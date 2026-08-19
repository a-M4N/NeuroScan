"""
Model loading and lifecycle management for the inference API.

Loads the tumor classifier + builds its Grad-CAM instance ONCE at app
startup, and exposes them as module-level singletons so routers can
reuse the same in-memory model across every request instead of
reloading weights per call.

Wire this up in api/main.py via FastAPI's lifespan:

    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from api.core import model_loader

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        model_loader.load()
        yield
        model_loader.unload()

    app = FastAPI(lifespan=lifespan)
"""

import logging
from pathlib import Path
from typing import Optional

import torch
from pytorch_grad_cam import GradCAM

from models.src.model import load_model, CLASS_LABELS
from api.core.gradcam import build_gradcam

logger = logging.getLogger(__name__)

# Default checkpoint location — override via load(checkpoint_path=...)
DEFAULT_CHECKPOINT_PATH = Path("models/checkpoints/tumor_classifier_brisc2025.pth")


class _ModelRegistry:
    """
    Holds the loaded model + Grad-CAM + device as module-level state.
    Not meant to be instantiated more than once per process.
    """

    def __init__(self) -> None:
        self.model: Optional[torch.nn.Module] = None
        self.cam: Optional[GradCAM] = None
        self.device: Optional[torch.device] = None
        self.class_labels: list[str] = CLASS_LABELS

    @property
    def is_loaded(self) -> bool:
        return self.model is not None


_registry = _ModelRegistry()


def load(checkpoint_path: Optional[Path] = None) -> None:
    """
    Load the model and build its Grad-CAM instance. Call once at app
    startup. Safe to call again to hot-swap a checkpoint (e.g. after
    retraining), though that's not a typical production path.
    """
    checkpoint_path = checkpoint_path or DEFAULT_CHECKPOINT_PATH

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Loading tumor classifier from {checkpoint_path} onto {device}")

    model = load_model(checkpoint_path, device=device)
    cam = build_gradcam(model)

    _registry.model = model
    _registry.cam = cam
    _registry.device = device

    logger.info(f"Model loaded successfully. Classes: {CLASS_LABELS}")


def unload() -> None:
    """Release model resources. Call on app shutdown."""
    _registry.model = None
    _registry.cam = None
    _registry.device = None
    logger.info("Model unloaded")


def get_model() -> torch.nn.Module:
    """
    Dependency-injectable accessor for the loaded model. Raises if
    called before load() — this is a startup-ordering bug, not a
    request-time error, so it fails loudly rather than silently
    returning None.
    """
    if not _registry.is_loaded:
        raise RuntimeError(
            "Model not loaded. Ensure model_loader.load() runs in the "
            "app's startup/lifespan handler before any request hits /predict."
        )
    return _registry.model


def get_cam() -> GradCAM:
    """Dependency-injectable accessor for the shared GradCAM instance."""
    if not _registry.is_loaded:
        raise RuntimeError(
            "Model not loaded. Ensure model_loader.load() runs in the "
            "app's startup/lifespan handler before any request hits /predict."
        )
    return _registry.cam


def get_device() -> torch.device:
    """Dependency-injectable accessor for the inference device."""
    if _registry.device is None:
        raise RuntimeError("Model not loaded — device unset.")
    return _registry.device