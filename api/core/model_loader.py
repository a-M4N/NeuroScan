import torch
from pytorch_grad_cam import GradCAM
from models.src.model import build_model, load_model, get_gradcam_target_layers
from models.src.disease_configs import DISEASE_CONFIGS, DiseaseConfig


class ModelRegistry:
    def __init__(self):
        self._models: dict[str, torch.nn.Module] = {}
        self._cams: dict[str, GradCAM] = {}
        self._device: torch.device | None = None
        self.is_loaded: bool = False

    def load_all(self):
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        for disease_type, cfg in DISEASE_CONFIGS.items():
            model = load_model(cfg.checkpoint_path, num_classes=cfg.num_classes)
            model.to(self._device)
            model.eval()
            self._models[disease_type] = model
            target_layers = get_gradcam_target_layers(model, cfg.gradcam_target_layer)
            self._cams[disease_type] = GradCAM(model=model, target_layers=target_layers)
        self.is_loaded = True

    def unload_all(self):
        self._models.clear()
        self._cams.clear()
        self.is_loaded = False

    def get_model(self, disease_type: str) -> torch.nn.Module:
        if disease_type not in self._models:
            raise ValueError(
                f"Unknown or unloaded disease_type '{disease_type}'. "
                f"Available: {sorted(self._models.keys())}"
            )
        return self._models[disease_type]

    def get_cam(self, disease_type: str) -> GradCAM:
        if disease_type not in self._cams:
            raise ValueError(
                f"Unknown or unloaded disease_type '{disease_type}'. "
                f"Available: {sorted(self._cams.keys())}"
            )
        return self._cams[disease_type]

    def get_config(self, disease_type: str) -> DiseaseConfig:
        return DISEASE_CONFIGS[disease_type]

    def get_device(self) -> torch.device:
        return self._device


_registry = ModelRegistry()

# --- module-level wrappers, so main.py / routers don't need to touch the class directly ---

def load():
    _registry.load_all()

def unload():
    _registry.unload_all()

def get_model(disease_type: str) -> torch.nn.Module:
    return _registry.get_model(disease_type)

def get_cam(disease_type: str) -> GradCAM:
    return _registry.get_cam(disease_type)

def get_config(disease_type: str) -> DiseaseConfig:
    return _registry.get_config(disease_type)

def get_device() -> torch.device:
    return _registry.get_device()