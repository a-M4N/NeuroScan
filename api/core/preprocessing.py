"""
Preprocessing pipeline for tumor classifier inference.

IMPORTANT: the transform pipeline here (resize -> grayscale-to-3ch ->
tensor -> normalize) mirrors `val_tf` from the training notebook EXACTLY.
If you change training preprocessing, update this file to match, or
predictions will silently degrade.

The model was trained on 2D JPEG slices (BRISC2025 dataset). The project
spec accepts NIfTI/DICOM volumes, so this module also provides a function
to extract a single representative 2D slice from a volume before running
it through the same image pipeline the model expects.
"""

from pathlib import Path
from typing import Union

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from models.src.model import IMG_SIZE, IMAGENET_MEAN, IMAGENET_STD

# --- Image transform (matches notebook's val_tf exactly) -------------------

val_tf = transforms.Compose([
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.Grayscale(num_output_channels=3),
    transforms.ToTensor(),
    transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
])


# --- Entry point used by the API --------------------------------------------

def preprocess(file_path: Union[str, Path], slice_index: int = None) -> torch.Tensor:
    """
    Load a scan (JPG/PNG, NIfTI, or DICOM) and return a model-ready tensor.

    Args:
        file_path: path to the input file.
        slice_index: which axial slice to use for NIfTI/DICOM volumes.
            Defaults to the middle slice if not given. Ignored for
            already-2D image formats (jpg/png).

    Returns:
        A (1, 3, IMG_SIZE, IMG_SIZE) tensor, batched and ready for
        model(input_tensor).
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in (".jpg", ".jpeg", ".png"):
        img = _load_2d_image(file_path)
    elif suffix in (".nii", ".gz") or file_path.name.endswith(".nii.gz"):
        img = _load_nifti_slice(file_path, slice_index)
    elif suffix == ".dcm" or _looks_like_dicom_dir(file_path):
        img = _load_dicom_slice(file_path, slice_index)
    else:
        raise ValueError(
            f"Unsupported file type: {file_path.suffix}. "
            "Expected .jpg/.png, .nii/.nii.gz, or .dcm"
        )

    input_tensor = val_tf(img).unsqueeze(0)
    return input_tensor


# --- Format-specific loaders -------------------------------------------------

def _load_2d_image(file_path: Path) -> Image.Image:
    """Load a standard 2D image file (jpg/png), matching notebook's img loading."""
    return Image.open(file_path).convert("RGB")


def _load_nifti_slice(file_path: Path, slice_index: int = None) -> Image.Image:
    """
    Load a NIfTI volume and extract a single axial slice as a PIL Image,
    normalized to 0-255 uint8 so it can go through the same val_tf as
    the training JPEGs.
    """
    import nibabel as nib

    volume = nib.load(str(file_path)).get_fdata()  # (H, W, D)

    if slice_index is None:
        slice_index = volume.shape[2] // 2  # middle axial slice

    slice_2d = volume[:, :, slice_index]
    return _array_to_pil(slice_2d)


def _load_dicom_slice(file_path: Path, slice_index: int = None) -> Image.Image:
    """
    Load a DICOM file (single slice) or a directory of DICOM files
    (full series) and extract one slice as a PIL Image.
    """
    import pydicom

    if file_path.is_dir():
        dicom_files = sorted(file_path.glob("*.dcm"))
        if not dicom_files:
            raise ValueError(f"No .dcm files found in {file_path}")
        if slice_index is None:
            slice_index = len(dicom_files) // 2
        ds = pydicom.dcmread(str(dicom_files[slice_index]))
    else:
        ds = pydicom.dcmread(str(file_path))

    slice_2d = ds.pixel_array.astype(np.float32)
    return _array_to_pil(slice_2d)


def _array_to_pil(slice_2d: np.ndarray) -> Image.Image:
    """Normalize a raw intensity slice to 0-255 uint8 and convert to RGB PIL Image."""
    slice_2d = slice_2d.astype(np.float32)
    min_val, max_val = slice_2d.min(), slice_2d.max()
    if max_val > min_val:
        slice_2d = (slice_2d - min_val) / (max_val - min_val) * 255.0
    else:
        slice_2d = np.zeros_like(slice_2d)
    slice_2d = slice_2d.astype(np.uint8)
    return Image.fromarray(slice_2d).convert("RGB")


def _looks_like_dicom_dir(file_path: Path) -> bool:
    return file_path.is_dir() and any(file_path.glob("*.dcm"))


# --- Helper for Grad-CAM (needs the raw resized RGB array, not normalized) --

def get_rgb_array_for_gradcam(file_path: Union[str, Path], slice_index: int = None) -> np.ndarray:
    """
    Return the resized RGB image as a float array in [0, 1], matching
    the `rgb_img` used in the notebook's Grad-CAM overlay step
    (show_cam_on_image expects this format).
    """
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()

    if suffix in (".jpg", ".jpeg", ".png"):
        img = _load_2d_image(file_path)
    elif suffix in (".nii", ".gz") or file_path.name.endswith(".nii.gz"):
        img = _load_nifti_slice(file_path, slice_index)
    elif suffix == ".dcm" or _looks_like_dicom_dir(file_path):
        img = _load_dicom_slice(file_path, slice_index)
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")

    rgb_img = np.array(img.resize((IMG_SIZE, IMG_SIZE))) / 255.0
    return rgb_img.astype(np.float32)