"""
Shared model architecture builder + checkpoint loader.

Disease-specific config (class labels, checkpoint paths, Grad-CAM target
layer) lives in models/src/disease_configs.py — NOT here. This module is
purely "given a num_classes, build/load an EfficientNet-B0."
"""

from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
import timm

IMG_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def build_model(num_classes: int, pretrained: bool = False) -> nn.Module:
    """Build an EfficientNet-B0 classifier architecture (untrained)."""
    return timm.create_model(
        "efficientnet_b0",
        pretrained=pretrained,
        num_classes=num_classes,
    )


def get_gradcam_target_layers(model: nn.Module, target_layer_name: str = "conv_head") -> list:
    """Return the target layer(s) for Grad-CAM. Same attr name across all
    our EfficientNet-B0 variants so far, but kept configurable per-disease."""
    return [getattr(model, target_layer_name)]


def load_model(
    checkpoint_path: str | Path,
    num_classes: int,
    device: Optional[torch.device] = None,
) -> nn.Module:
    """Build the model and load fine-tuned weights from a checkpoint."""
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