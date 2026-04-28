"""
Recursive folder scanner with multiprocessing, checkpoints, and streaming output.

Designed for very large workloads (100k+ files): each worker process loads
its own ONNX session; progress is checkpointed per-file so an interrupted
run can resume.

Public API:
    scan_folder(root, model_path, output_path, ...) -> int (number of detections)
"""

import json
import logging
import os
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import set_start_method
from pathlib import Path

import cv2
import numpy as np

from detector import DEFAULT_IMGSZ, DEFAULT_THRESHOLD, detect_stamps, load_onnx_model, quick_reject
from reporter import StreamingExcelWriter

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}

# Per-worker globals — initialised once per process via _worker_init
_WORKER_SESSION = None
_WORKER_CONFIG: dict = {}


def _worker_init(model_path: str, config: dict) -> None:
    """Runs once per worker process. Loads ONNX session into a global."""
    global _WORKER_SESSION, _WORKER_CONFIG
    # Ignore SIGINT in workers — let the parent handle Ctrl+C
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    _WORKER_SESSION = load_onnx_model(model_path)
    _WORKER_CONFIG = config


def _imread_unicode(path: Path) -> np.ndarray | None:
    """cv2.imread that handles Unicode/Cyrillic paths on Windows."""
    try:
        data = path.read_bytes()
        arr = np.frombuffer(data, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


def _process_image(file_path: Path) -> list[dict]:
    img = _imread_unicode(file_path)
    if img is None:
        return []
    if _WORKER_CONFIG.get("prefilter") and quick_reject(img):
        return []
    detections = detect_stamps(
        img,
        _WORKER_SESSION,
        threshold=_WORKER_CONFIG["threshold"],
        imgsz=_WORKER_CONFIG["imgsz"],
    )
    if not detections:
        return []
    return [{
        "file": str(file_path),
        "file_name": file_path.name,
        "folder": str(file_path.parent),
        "file_type": "IMAGE",
        "page": 1,
        "total_pages": 1,
        "detections": detections,
    }]


def _process_pdf(file_path: Path) -> list[dict]:
    try:
        import fitz
    except ImportError:
        return []

    results = []
    dpi = _WORKER_CONFIG["pdf_dpi"]
    matrix_scale = dpi / 72.0
    do_prefilter = _WORKER_CONFIG.get("prefilter", False)

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        logging.exception(f"Failed to open PDF {file_path}: {exc}")
        return []

    try:
        import fitz as _fitz
        mat = _fitz.Matrix(matrix_scale, matrix_scale)
        total = len(doc)
        for page_num in range(total):
            try:
                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif pix.n == 1:
                    img = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                else:
                    img = arr

                if do_prefilter and quick_reject(img):
                    continue

                detections = detect_stamps(
                    img,
                    _WORKER_SESSION,
                    threshold=_WORKER_CONFIG["threshold"],
                    imgsz=_WORKER_CONFIG["imgsz"],
                )
                if detections:
                    results.append({
                        "file": str(file_path),
                        "file_name": file_path.name,
                        "folder": str(file_path.parent),
                        "file_type": "PDF",
                        "page": page_num + 1,
                        "total_pages": total,
                        "detections": detections,
                    })
            except Exception as exc:
                logging.exception(f"Page {page_num + 1} of {file_path} failed: {exc}")
    finally:
        doc.close()

    return results


def _process_file(file_path_str: str) -> tuple[str, list[dict], float]:
    """Worker entry point. Returns (path, results, elapsed_seconds)."""
    fp = Path(file_path_str)
    t0 = time.time()
    try:
        ext = fp.suffix.lower()
        if ext in PDF_EXTENSIONS:
            results = _process_pdf(fp)
        else:
            results = _process_image(fp)
    except Exception as exc:
        logging.exception(f"{fp}: {exc}")
        results = []
    return file_path_str, results, time.time() - t0


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        with open(path) as f:
            data = json.load(f)
        return set(data.get("done", []))
    except Exception:
        return set()


def _save_checkpoint(path: Path, done: set[str]) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        with open(tmp, "w") as f:
            json.dump({"done": sorted(done)}, f)
        os.replace(tmp, path)
    except Exception as exc:
        logging.warning(f"Checkpoint save failed: {exc}")


def scan_folder(
    root_folder: str | Path,
    model_path: str | Path,
    output_path: str | Path,
    threshold: float = DEFAULT_THRESHOLD,
    imgsz: int = DEFAULT_IMGSZ,
    workers: int | None = None,
    pdf_dpi: int = 150,
    prefilter: bool = False,
    resume: bool = True,
    log_path: str | Path = "scan.log",
) -> int:
    """
    Scan a folder recursively and write detections to an Excel report as they
    arrive. Returns the total number of detections written.
    """
    try:
        set_start_method("spawn", force=False)
    except RuntimeError:
        pass  # already set

    root = Path(root_folder).resolve()
    output_path = Path(output_path).resolve()
    log_path = Path(log_path).resolve()
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".checkpoint.json")

    # Reset logger handlers to avoid duplicates on re-runs
    for h in list(logging.root.handlers):
        logging.root.removeHandler(h)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if workers is None:
        workers = max(1, (os.cpu_count() or 2) - 1)

    config = {
        "threshold": threshold,
        "imgsz": imgsz,
        "pdf_dpi": pdf_dpi,
        "prefilter": prefilter,
    }

    # Discover files
    print(f"Scanning {root} for files...")
    all_files = [
        f for f in root.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS | PDF_EXTENSIONS
    ]
    print(f"  Total candidate files: {len(all_files):,}")

    done: set[str] = set()
    if resume:
        done = _load_checkpoint(checkpoint_path)
        if done:
            print(f"  Resuming: {len(done):,} files already processed")

    pending = [f for f in all_files if str(f) not in done]
    print(f"  Files to process now: {len(pending):,}")
    print(f"  Workers: {workers}")
    print(f"  Model: {model_path}")
    print(f"  Output: {output_path}")
    print(f"  Log: {log_path}")
    print()

    if not pending:
        print("Nothing to do.")
        return 0

    writer = StreamingExcelWriter(output_path)
    total_detections = 0
    processed_now = 0
    t_start = time.time()

    try:
        from tqdm import tqdm
        pbar = tqdm(total=len(pending), unit="file", smoothing=0.05)
    except ImportError:
        pbar = None

    try:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(str(model_path), config),
        ) as pool:
            futures = {pool.submit(_process_file, str(fp)): fp for fp in pending}

            for future in as_completed(futures):
                try:
                    fp_str, results, elapsed = future.result()
                except Exception as exc:
                    logging.exception(f"Worker failure: {exc}")
                    continue

                done.add(fp_str)
                processed_now += 1

                for r in results:
                    writer.add_detection(r)
                    total_detections += len(r["detections"])

                if pbar is not None:
                    pbar.set_postfix(hits=total_detections, refresh=False)
                    pbar.update(1)

                # Periodic checkpoint flush
                if processed_now % 50 == 0:
                    _save_checkpoint(checkpoint_path, done)

                if elapsed > 30:
                    logging.info(f"Slow file ({elapsed:.1f}s): {fp_str}")

    except KeyboardInterrupt:
        print("\nInterrupted. Saving progress…")
    finally:
        if pbar is not None:
            pbar.close()
        _save_checkpoint(checkpoint_path, done)
        writer.close()

    elapsed_total = time.time() - t_start
    print(f"\nProcessed {processed_now:,} files in {elapsed_total/60:.1f} minutes")
    print(f"Detections written: {total_detections:,}")
    print(f"Report: {output_path}")
    if pending and processed_now < len(pending):
        print(f"Resume by running again with --resume (default).")

    return total_detections
