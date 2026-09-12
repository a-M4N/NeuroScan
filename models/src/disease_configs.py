"""
Per-disease model configuration. Single source of truth for class labels,
checkpoint paths, and Grad-CAM target layers across training and inference.

Both models/src/train.py (per-disease training scripts) and
api/core/model_loader.py should import from here.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiseaseConfig:
    disease_type: str
    checkpoint_path: str
    class_labels: list[str]
    negative_class: str | None
    gradcam_target_layer: str = "conv_head"
    region_mapping_enabled: bool = False  # opt-in for affected_region derivation
    severity_order: list[str] | None = None  # optional ordered list from least severe to most severe

    @property
    def num_classes(self) -> int:
        return len(self.class_labels)


DISEASE_CONFIGS: dict[str, DiseaseConfig] = {
    "brain_tumor": DiseaseConfig(
        disease_type="brain_tumor",
        checkpoint_path="models/checkpoints/tumor_classifier_brisc2025.pth",
        class_labels=["glioma", "meningioma", "no_tumor", "pituitary"],
        negative_class="no_tumor",
        region_mapping_enabled=True,  # localization is clinically meaningful here
        severity_order=None,  # distinct tumor histologies, not a linear severity spectrum
    ),
    "alzheimers": DiseaseConfig(
        disease_type="alzheimers",
        checkpoint_path="models/checkpoints/alzheimers_effnet_b0.pth",
        class_labels=["non_demented", "very_mild_demented", "mild_demented", "moderate_demented"],
        negative_class="non_demented",
        # region_mapping_enabled left as default False — Alzheimer's staging is diffuse
        severity_order=["non_demented", "very_mild_demented", "mild_demented", "moderate_demented"],
    ),
}