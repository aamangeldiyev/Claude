"""
YOLO ONNX-based stamp detector.

Loads a YOLOv8 ONNX model and runs inference on images. Returns detections
in the same dict format used elsewhere in the project.

Public API:
    load_onnx_model(path) -> session
    detect_stamps(image, session, threshold=0.35, imgsz=640) -> list[dict]
    quick_reject(image) -> bool   (optional empty-page filter)
"""

from pathlib import Path

import cv2
import numpy as np

DEFAULT_THRESHOLD = 0.35
DEFAULT_NMS_THRESHOLD = 0.45
DEFAULT_IMGSZ = 640


def load_onnx_model(model_path: str | Path):
    """Load an ONNX model with onnxruntime. Returns a session."""
    import onnxruntime as ort

    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"ONNX model not found: {path}")

    # CPU only — on the target machine we don't assume GPU.
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1   # leave parallelism to ProcessPoolExecutor
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(
        str(path),
        sess_options=so,
        providers=["CPUExecutionProvider"],
    )


def _letterbox(img: np.ndarray, new_size: int = DEFAULT_IMGSZ) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize image while preserving aspect ratio, padding with grey."""
    h, w = img.shape[:2]
    r = min(new_size / h, new_size / w)
    new_w = int(round(w * r))
    new_h = int(round(h * r))
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    canvas = np.full((new_size, new_size, 3), 114, dtype=np.uint8)
    pad_x = (new_size - new_w) // 2
    pad_y = (new_size - new_h) // 2
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, r, (pad_x, pad_y)


def quick_reject(image: np.ndarray, std_threshold: float = 4.0) -> bool:
    """
    Fast pre-filter: returns True if the page is essentially blank
    (very low pixel std). Use only on pages where missing a stamp on
    a near-blank page is acceptable.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    # Downsample for speed; std on a scaled-down image is a good proxy.
    small = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
    return float(small.std()) < std_threshold


def detect_stamps(
    image: np.ndarray,
    session,
    threshold: float = DEFAULT_THRESHOLD,
    nms_threshold: float = DEFAULT_NMS_THRESHOLD,
    imgsz: int = DEFAULT_IMGSZ,
) -> list[dict]:
    """
    Run YOLO inference and return detections in the project's dict format.
    Each detection: {"method": "YOLO", "confidence": float, "bbox": (x1,y1,x2,y2),
                     "template_name": "stamp"}
    """
    if image is None or image.size == 0:
        return []

    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    orig_h, orig_w = image.shape[:2]

    canvas, ratio, (pad_x, pad_y) = _letterbox(image, imgsz)

    # BGR → RGB, HWC → CHW, float32 [0,1], add batch dim
    blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    blob = blob.transpose(2, 0, 1)[None]  # (1, 3, H, W)

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: blob})
    pred = outputs[0]  # YOLOv8 export shape: (1, 4 + nc, num_anchors)

    # Squeeze batch, transpose to (num_anchors, 4 + nc)
    pred = np.squeeze(pred, axis=0).T  # (num_anchors, 4 + nc)

    # First 4 cols: cx, cy, w, h (in letterboxed pixel space)
    boxes_xywh = pred[:, :4]
    scores_per_class = pred[:, 4:]
    class_scores = scores_per_class.max(axis=1)
    class_ids = scores_per_class.argmax(axis=1)

    keep = class_scores >= threshold
    if not keep.any():
        return []

    boxes_xywh = boxes_xywh[keep]
    class_scores = class_scores[keep]
    class_ids = class_ids[keep]

    # Convert (cx, cy, w, h) → (x1, y1, w, h) for cv2 NMS
    cx = boxes_xywh[:, 0]; cy = boxes_xywh[:, 1]
    bw = boxes_xywh[:, 2]; bh = boxes_xywh[:, 3]
    x1 = cx - bw / 2; y1 = cy - bh / 2

    nms_boxes = np.stack([x1, y1, bw, bh], axis=1).astype(np.float32)
    indices = cv2.dnn.NMSBoxes(
        nms_boxes.tolist(),
        class_scores.tolist(),
        score_threshold=threshold,
        nms_threshold=nms_threshold,
    )

    if len(indices) == 0:
        return []

    indices = np.array(indices).flatten()

    detections = []
    for i in indices:
        # Box still in letterboxed coordinates — undo letterbox
        bx1 = (x1[i] - pad_x) / ratio
        by1 = (y1[i] - pad_y) / ratio
        bx2 = (x1[i] + bw[i] - pad_x) / ratio
        by2 = (y1[i] + bh[i] - pad_y) / ratio
        bx1 = max(0, int(round(bx1))); by1 = max(0, int(round(by1)))
        bx2 = min(orig_w, int(round(bx2))); by2 = min(orig_h, int(round(by2)))
        if bx2 <= bx1 or by2 <= by1:
            continue

        detections.append({
            "method": "YOLO",
            "confidence": round(float(class_scores[i]), 4),
            "bbox": (bx1, by1, bx2, by2),
            "template_name": f"stamp" if int(class_ids[i]) == 0 else f"class_{int(class_ids[i])}",
        })

    return detections
