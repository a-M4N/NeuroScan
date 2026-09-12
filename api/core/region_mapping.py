"""
Coarse anatomical/positional region mapping from Grad-CAM activation heatmaps.

Derives a high-level position label (e.g. 'upper-left region', 'central-right region')
from the weighted activation centroid of a 2D Grad-CAM heatmap.

NOTE: This is a coordinate/position-based heuristic relative to the 2D image frame,
not a radiologically confirmed anatomical orientation (which requires DICOM orientation
tags / stereotaxic atlas registration).
"""

from typing import Optional, TypedDict
import numpy as np


class RegionResult(TypedDict):
    affected_region: Optional[str]
    centroid: Optional[dict[str, float]]
    relative_coordinates: Optional[dict[str, float]]


def derive_affected_region(
    grayscale_cam: np.ndarray,
    activation_threshold_ratio: float = 0.4,
) -> RegionResult:
    """
    Compute the weighted centroid of Grad-CAM activations and map it
    to a coarse 2D positional region label.

    Args:
        grayscale_cam: 2D numpy array of shape (H, W) with float values in [0, 1].
        activation_threshold_ratio: Minimum ratio of peak activation to consider
            when calculating the centroid (filters out background diffuse noise).

    Returns:
        RegionResult dictionary containing:
          - affected_region: Human-readable region label (e.g. 'upper-left region') or None.
          - centroid: {'x': float, 'y': float} pixel coordinates or None.
          - relative_coordinates: {'norm_x': float, 'norm_y': float} in [0, 1] or None.
    """
    if grayscale_cam is None or grayscale_cam.size == 0:
        return {"affected_region": None, "centroid": None, "relative_coordinates": None}

    max_val = float(np.max(grayscale_cam))
    if max_val < 0.1:
        # Diffuse/negligible activation
        return {"affected_region": None, "centroid": None, "relative_coordinates": None}

    threshold = max_val * activation_threshold_ratio
    weights = np.where(grayscale_cam >= threshold, grayscale_cam, 0.0)
    total_weight = float(np.sum(weights))

    if total_weight <= 0.0:
        return {"affected_region": None, "centroid": None, "relative_coordinates": None}

    h, w = grayscale_cam.shape
    y_indices, x_indices = np.indices((h, w), dtype=np.float32)

    cy = float(np.sum(y_indices * weights) / total_weight)
    cx = float(np.sum(x_indices * weights) / total_weight)

    norm_y = cy / h  # 0.0 (top) to 1.0 (bottom)
    norm_x = cx / w  # 0.0 (left) to 1.0 (right)

    # Vertical split: upper (<0.38), central (0.38 - 0.62), lower (>0.62)
    if norm_y < 0.38:
        v_label = "upper"
    elif norm_y > 0.62:
        v_label = "lower"
    else:
        v_label = "central"

    # Horizontal split: left (<0.38), central (0.38 - 0.62), right (>0.62)
    if norm_x < 0.38:
        h_label = "left"
    elif norm_x > 0.62:
        h_label = "right"
    else:
        h_label = "central"

    if v_label == "central" and h_label == "central":
        region_str = "central region"
    elif v_label == "central":
        region_str = f"central-{h_label} region"
    elif h_label == "central":
        region_str = f"{v_label}-central region"
    else:
        region_str = f"{v_label}-{h_label} region"

    return {
        "affected_region": region_str,
        "centroid": {"x": round(cx, 2), "y": round(cy, 2)},
        "relative_coordinates": {"norm_x": round(norm_x, 3), "norm_y": round(norm_y, 3)},
    }
