"""
Recursive folder scanner with multiprocessing, checkpoints, and streaming output.

Designed for large workloads (100k+ files). Each worker process loads its own
copy of templates; progress is checkpointed per-file so an interrupted run
can resume without reprocessing completed files.
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

from detector import DEFAULT_THRESHOLD, detect_stamps, load_templates
from reporter import StreamingExcelWriter

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
PDF_EXTENSIONS = {".pdf"}

PDF_DPI_DEFAULT = 100  # fast default; use --pdf-dpi 150 for higher quality

# Per-worker globals — initialised once per process via _worker_init
_WORKER_TEMPLATES: list[dict] = []
_WORKER_CONFIG: dict = {}


def _worker_init(stamps_dir: str, config: dict) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    global _WORKER_TEMPLATES, _WORKER_CONFIG
    _WORKER_TEMPLATES = load_templates(stamps_dir)
    _WORKER_CONFIG = config


def _imread_unicode(path: Path) -> np.ndarray | None:
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
    detections = detect_stamps(img, _WORKER_TEMPLATES, _WORKER_CONFIG["threshold"])
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

    dpi = _WORKER_CONFIG.get("pdf_dpi", PDF_DPI_DEFAULT)
    mat_scale = dpi / 72.0
    results = []

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        logging.error(f"Cannot open PDF {file_path}: {exc}")
        return []

    try:
        mat = fitz.Matrix(mat_scale, mat_scale)
        total = len(doc)
        for page_num in range(total):
            try:
                pix = doc[page_num].get_pixmap(matrix=mat)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif pix.n == 1:
                    img = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                else:
                    img = arr

                detections = detect_stamps(img, _WORKER_TEMPLATES, _WORKER_CONFIG["threshold"])
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
                logging.error(f"{file_path} page {page_num + 1}: {exc}")
    finally:
        doc.close()

    return results


def _process_file(path_str: str) -> tuple[str, list[dict], float]:
    fp = Path(path_str)
    t0 = time.time()
    try:
        if fp.suffix.lower() in PDF_EXTENSIONS:
            results = _process_pdf(fp)
        else:
            results = _process_image(fp)
    except Exception as exc:
        logging.error(f"{fp}: {exc}")
        results = []
    return path_str, results, time.time() - t0


def _load_checkpoint(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        return set(json.loads(path.read_text()).get("done", []))
    except Exception:
        return set()


def _save_checkpoint(path: Path, done: set[str]) -> None:
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps({"done": sorted(done)}))
        os.replace(tmp, path)
    except Exception as exc:
        logging.warning(f"Checkpoint save failed: {exc}")


def scan_folder(
    root_folder: str | Path,
    stamps_dir: str | Path,
    output_path: str | Path,
    threshold: float = DEFAULT_THRESHOLD,
    workers: int | None = None,
    pdf_dpi: int = PDF_DPI_DEFAULT,
    resume: bool = True,
    log_path: str | Path = "scan.log",
    progress_callback=None,
    cancel_event=None,
) -> int:
    """
    Scan root_folder recursively, write detections to Excel as they arrive.
    Returns total number of detections written.

    progress_callback: optional callable(processed, total, hits, last_file) for UI updates.
    cancel_event: optional threading.Event — if set, scan stops cleanly.
    """
    try:
        set_start_method("spawn", force=False)
    except RuntimeError:
        pass

    root = Path(root_folder).resolve()
    output_path = Path(output_path).resolve()
    checkpoint_path = output_path.with_suffix(output_path.suffix + ".checkpoint.json")

    for h in list(logging.root.handlers):
        logging.root.removeHandler(h)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    if workers is None:
        workers = max(1, (os.cpu_count() or 2) - 1)

    # Validate stamps
    templates = load_templates(str(stamps_dir))
    if not templates:
        print(f"[ERROR] No stamp images found in '{stamps_dir}'.", file=sys.stderr)
        print( "        Add PNG/JPG screenshots of stamps there.", file=sys.stderr)
        return 0
    print(f"Loaded {len(templates)} stamp template(s).")

    config = {"threshold": threshold, "pdf_dpi": pdf_dpi}

    # Discover files
    print(f"Scanning {root} ...")
    all_files = [
        f for f in root.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS | PDF_EXTENSIONS
    ]
    print(f"  Total files found : {len(all_files):,}")

    done: set[str] = _load_checkpoint(checkpoint_path) if resume else set()
    if done:
        print(f"  Already processed : {len(done):,} (resuming)")

    pending = [f for f in all_files if str(f) not in done]
    print(f"  To process now    : {len(pending):,}")
    print(f"  Workers           : {workers}  |  PDF DPI: {pdf_dpi}  |  Threshold: {threshold}")
    print()

    if not pending:
        print("Nothing left to process.")
        if progress_callback:
            progress_callback(0, 0, 0, "Nothing to process")
        return 0

    writer = StreamingExcelWriter(output_path)
    total_detections = 0
    processed = 0
    t_start = time.time()

    if progress_callback:
        progress_callback(0, len(pending), 0, "Starting...")

    try:
        from tqdm import tqdm
        pbar = tqdm(total=len(pending), unit="file", smoothing=0.05)
    except ImportError:
        pbar = None

    try:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(str(stamps_dir), config),
        ) as pool:
            futures = {pool.submit(_process_file, str(fp)): fp for fp in pending}
            for future in as_completed(futures):
                if cancel_event is not None and cancel_event.is_set():
                    print("\nCancellation requested...")
                    for f in futures:
                        f.cancel()
                    break
                try:
                    path_str, results, elapsed = future.result()
                except Exception as exc:
                    logging.error(f"Worker error: {exc}")
                    continue

                done.add(path_str)
                processed += 1

                for r in results:
                    writer.add_detection(r)
                    total_detections += len(r["detections"])

                if pbar:
                    pbar.set_postfix(hits=total_detections, refresh=False)
                    pbar.update(1)

                if progress_callback:
                    progress_callback(processed, len(pending), total_detections, Path(path_str).name)

                if processed % 50 == 0:
                    _save_checkpoint(checkpoint_path, done)

                if elapsed > 60:
                    logging.info(f"Slow file ({elapsed:.0f}s): {path_str}")

    except KeyboardInterrupt:
        print("\nInterrupted — saving progress...")
    finally:
        if pbar:
            pbar.close()
        _save_checkpoint(checkpoint_path, done)
        writer.close()

    elapsed_total = time.time() - t_start
    print(f"\nProcessed {processed:,} files in {elapsed_total / 60:.1f} min")
    print(f"Detections: {total_detections:,}  |  Report: {output_path}")
    if processed < len(pending):
        print("Run again to resume from where it stopped.")

    return total_detections
