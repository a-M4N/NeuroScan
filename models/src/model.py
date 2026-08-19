"""
Tumor classifier model definition.

Architecture: EfficientNet-B0 (timm), fine-tuned for 4-class brain tumor
classification on the BRISC2025 dataset.

This module is the single source of truth for the model architecture and
class labels. Both training code (models/src/train.py) and the inference
API (api/core/model_loader.py) should import from here, so the two never
drift apart.
"""

from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import timm

# --- Constants -------------------------------------------------------------

# Confirmed class order from training (alphabetical, as produced by
# torchvision.datasets.ImageFolder / full_train.classes)
CLASS_LABELS = ["glioma", "meningioma", "no_tumor", "pituitary"]
NUM_CLASSES = len(CLASS_LABELS)

IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

# Layer used as the Grad-CAM target (last conv block before the classifier
# head in EfficientNet-B0 via timm)
GRADCAM_TARGET_LAYER_NAME = "conv_head"


# --- Model builder -----------------------------------------------------------

def build_model(num_classes: int = NUM_CLASSES, pretrained: bool = False) -> nn.Module:
    """
    Build the EfficientNet-B0 tumor classifier architecture (untrained).

    Args:
        num_classes: number of output classes. Defaults to 4
            (glioma / meningioma / no_tumor / pituitary).
        pretrained: whether to load ImageNet-pretrained backbone weights.
            Use True only when training from scratch; use False (default)
            when you're about to load your own fine-tuned checkpoint.

    Returns:
        An uninitialized (or ImageNet-initialized) timm EfficientNet-B0 model.
    """
    model = timm.create_model(
        "efficientnet_b0",
        pretrained=pretrained,
        num_classes=num_classes,
    )
    return model


def get_gradcam_target_layers(model: nn.Module) -> list:
    """Return the target layer(s) for Grad-CAM, matching training-time setup."""
    return [getattr(model, GRADCAM_TARGET_LAYER_NAME)]


# --- Checkpoint loading ------------------------------------------------------

def load_model(
    checkpoint_path: str | Path,
    device: Optional[torch.device] = None,
    num_classes: int = NUM_CLASSES,
) -> nn.Module:
    """
    Build the model and load fine-tuned weights from a checkpoint.

    Args:
        checkpoint_path: path to a .pth state_dict file
            (e.g. models/checkpoints/tumor_classifier_brisc2025.pth).
        device: torch device to load onto. Defaults to CUDA if available,
            else CPU.
        num_classes: must match the checkpoint's output layer size.

    Returns:
        Model in eval() mode, on the target device, ready for inference.
    """
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    checkpoint_path = Path(checkpoint_path)
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    model = build_model(num_classes=num_classes, pretrained=False)
    state_dict = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state_dict)
    model = model.to(device)
    model.eval()

    return model