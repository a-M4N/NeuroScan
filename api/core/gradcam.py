"""
Grad-CAM heatmap generation for the tumor classifier.

Mirrors the notebook's Grad-CAM cells: uses pytorch-grad-cam with
`model.conv_head` as the target layer, overlays the CAM on the resized
RGB slice, and returns a saveable heatmap image.
"""

import io
import uuid
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
from pytorch_grad_cam.utils.image import show_cam_on_image

from models.src.model import get_gradcam_target_layers, CLASS_LABELS

# Where generated heatmaps get written so they can be served/attached to reports
HEATMAP_OUTPUT_DIR = Path("data/heatmaps")


def build_gradcam(model: torch.nn.Module) -> GradCAM:
    """
    Construct a GradCAM object for the given model, using the same
    target layer (model.conv_head) as the training notebook.

    Build this once alongside the model at startup (in model_loader.py)
    and reuse it across requests rather than re-instantiating per call.
    """
    target_layers = get_gradcam_target_layers(model)
    return GradCAM(model=model, target_layers=target_layers)


def generate_heatmap(
    cam: GradCAM,
    input_tensor: torch.Tensor,
    rgb_img: np.ndarray,
    predicted_class_idx: int,
    save: bool = True,
    output_dir: Optional[Path] = None,
) -> dict:
    """
    Run Grad-CAM for the predicted class and overlay it on the input slice.

    Args:
        cam: GradCAM instance from build_gradcam().
        input_tensor: preprocessed (1, 3, H, W) normalized tensor,
            same one passed to model() for prediction.
        rgb_img: the un-normalized (H, W, 3) float array in [0, 1],
            from preprocessing.get_rgb_array_for_gradcam().
        predicted_class_idx: the class index the model predicted —
            Grad-CAM is generated with respect to this class.
        save: whether to write the overlay PNG to disk.
        output_dir: directory to save into. Defaults to HEATMAP_OUTPUT_DIR.

    Returns:
        {
          "heatmap_path": str | None,   # path on disk, if save=True
          "heatmap_array": np.ndarray,  # (H, W, 3) uint8 overlay, in-memory
        }
    """
    if predicted_class_idx == CLASS_LABELS.index("no_tumor"):
        # No tumor predicted — nothing meaningful to localize.
        # Caller should generally skip calling this in that case, but
        # guard here too so it fails safe rather than producing a
        # misleading heatmap on healthy scans.
        return {"heatmap_path": None, "heatmap_array": None}

    targets = [ClassifierOutputTarget(predicted_class_idx)]

    grayscale_cam = cam(input_tensor=input_tensor, targets=targets)
    grayscale_cam = grayscale_cam[0, :]  # first (only) image in batch

    overlay = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)  # uint8 (H, W, 3)

    heatmap_path = None
    if save:
        out_dir = output_dir or HEATMAP_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gradcam_{uuid.uuid4().hex[:12]}.png"
        heatmap_path = out_dir / filename
        Image.fromarray(overlay).save(heatmap_path)

    return {
        "heatmap_path": str(heatmap_path) if heatmap_path else None,
        "heatmap_array": overlay,
    }


def heatmap_to_bytes(heatmap_array: np.ndarray) -> bytes:
    """Convert a heatmap array to PNG bytes, e.g. for returning inline in an API response."""
    buf = io.BytesIO()
    Image.fromarray(heatmap_array).save(buf, format="PNG")
    return buf.getvalue()