"""
Grad-CAM heatmap generation — disease-agnostic as of Phase 5.

Mirrors the training notebooks' Grad-CAM cells: uses pytorch-grad-cam
with a configurable target layer (per DiseaseConfig.gradcam_target_layer),
overlays the CAM on the resized RGB slice, and returns a saveable
heatmap image.
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
from scipy import ndimage

from models.src.model import get_gradcam_target_layers

# Where generated heatmaps get written so they can be served/attached to reports
HEATMAP_OUTPUT_DIR = Path("data/heatmaps")

def _mask_background(
    grayscale_cam: np.ndarray,
    rgb_img: np.ndarray,
    brightness_threshold: float = 0.15,
    erosion_pixels: int = 12,
) -> np.ndarray:
    """
    Zero out Grad-CAM activation outside the brain, using connected-component
    analysis + erosion rather than a raw per-pixel brightness cutoff.

    A simple brightness threshold can't distinguish "background" from
    "skull/scalp" — both are often bright enough to pass a naive cutoff,
    while some genuine dark brain tissue (ventricles, sulci) can fall below
    it. Instead:
      1. Threshold on brightness to get a rough binary "is this the head" mask.
      2. Keep only the LARGEST connected bright region (the head), discarding
         small bright specks/noise elsewhere in the image.
      3. Erode that region inward by `erosion_pixels`, shrinking the mask
         boundary so it excludes the skull/scalp rim specifically, not just
         "anything dark."
      4. Zero out grayscale_cam wherever the eroded mask is False.

    Args:
        grayscale_cam: (H, W) float array in [0, 1], raw CAM output.
        rgb_img: (H, W, 3) float array in [0, 1], same image the CAM was
            computed on.
        brightness_threshold: initial cutoff to separate "head" from
            true black background. Kept low (0.15) since this step only
            needs to roughly outline the head, not fine-tune anything —
            the erosion step does the real work of excluding the rim.
        erosion_pixels: how many pixels to shrink the head mask inward.
            Larger = more aggressive exclusion of skull/scalp edge, but
            can also start cutting into real peripheral brain tissue if
            pushed too high.

    Returns:
        A copy of grayscale_cam with everything outside the eroded head
        region zeroed. Falls back to threshold-only masking if connected-
        component analysis finds no valid region (shouldn't normally happen).
    """
    brightness = rgb_img.mean(axis=-1)  # (H, W)
    binary = brightness >= brightness_threshold

    labeled, num_features = ndimage.label(binary)
    if num_features == 0:
        # Nothing passed the brightness threshold at all — return as-is
        # rather than zeroing everything, so we fail safe (no localization
        # lost) rather than silently returning an all-black heatmap.
        return grayscale_cam

    # Find the largest connected component by pixel count (the head),
    # ignoring label 0 which is background.
    sizes = ndimage.sum(binary, labeled, range(1, num_features + 1))
    largest_label = int(np.argmax(sizes)) + 1
    head_mask = labeled == largest_label

    if erosion_pixels > 0:
        head_mask = ndimage.binary_erosion(
            head_mask, iterations=erosion_pixels
        )

    return np.where(head_mask, grayscale_cam, 0.0)

def build_gradcam(model: torch.nn.Module, target_layer_name: str = "conv_head") -> GradCAM:
    """
    Construct a GradCAM object for the given model.

    target_layer_name is configurable per-disease via
    DiseaseConfig.gradcam_target_layer (see models/src/disease_configs.py) —
    all our EfficientNet-B0 variants use "conv_head" so far, but this
    isn't hardcoded in case a future disease model needs a different layer.

    Build this once alongside the model at startup (in model_loader.py)
    and reuse it across requests rather than re-instantiating per call.
    """
    target_layers = get_gradcam_target_layers(model, target_layer_name)
    return GradCAM(model=model, target_layers=target_layers)


def generate_heatmap(
    cam: GradCAM,
    input_tensor: torch.Tensor,
    rgb_img: np.ndarray,
    predicted_class_idx: int,
    negative_class_idx: Optional[int] = None,
    save: bool = True,
    output_dir: Optional[Path] = None,
    brightness_threshold: float = 0.15,
    erosion_pixels: int = 12,
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
        negative_class_idx: index of this disease's "negative"/healthy
            class (e.g. "no_tumor" or "non_demented"), if any. Pass
            cfg.class_labels.index(cfg.negative_class) from the caller.
            This is a fail-safe only — the router in predict.py already
            skips calling this function entirely for the negative class
            via cfg.negative_class, but guarding here too means this
            function fails safe even if called directly elsewhere.
        save: whether to write the overlay PNG to disk.
        output_dir: directory to save into. Defaults to HEATMAP_OUTPUT_DIR.

    Returns:
        {
          "heatmap_path": str | None,   # path on disk, if save=True
          "heatmap_array": np.ndarray,  # (H, W, 3) uint8 overlay, in-memory
        }
    """
    if negative_class_idx is not None and predicted_class_idx == negative_class_idx:
        # Negative/healthy class predicted — nothing meaningful to localize.
        return {"heatmap_path": None, "heatmap_array": None, "grayscale_cam": None}

    targets = [ClassifierOutputTarget(predicted_class_idx)]

    grayscale_cam = cam(input_tensor=input_tensor, targets=targets)
    grayscale_cam = grayscale_cam[0, :]  # first (only) image in batch

    # NEW — mask out background/skull-edge activation so heatmaps and
    # downstream region derivation don't localize outside the brain.
    grayscale_cam = _mask_background(grayscale_cam, rgb_img, brightness_threshold=brightness_threshold, erosion_pixels=erosion_pixels)

    overlay = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)  # uint8 (H, W, 3)

    heatmap_path = None
    heatmap_url = None
    if save:
        out_dir = output_dir or HEATMAP_OUTPUT_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = f"gradcam_{uuid.uuid4().hex[:12]}.png"
        heatmap_path = out_dir / filename
        Image.fromarray(overlay).save(heatmap_path)
        try:
            heatmap_url = heatmap_path.relative_to(Path("data")).as_posix()
        except ValueError:
            heatmap_url = Path("heatmaps", filename).as_posix()

    return {
        "heatmap_path": heatmap_path.as_posix() if heatmap_path else None,
        "heatmap_url": heatmap_url,
        "heatmap_array": overlay,
        "grayscale_cam": grayscale_cam,
    }


def heatmap_to_bytes(heatmap_array: np.ndarray) -> bytes:
    """Convert a heatmap array to PNG bytes, e.g. for returning inline in an API response."""
    buf = io.BytesIO()
    Image.fromarray(heatmap_array).save(buf, format="PNG")
    return buf.getvalue()