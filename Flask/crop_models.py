from __future__ import annotations

import io
import json
import logging
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

from model import Prediction


logger = logging.getLogger(__name__)


class CropModelRegistry:
    """Lazy loader for independently trained crop-specific disease models."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()
        self.registry_path = self.project_root / "Models" / "registry.json"
        self._registry_mtime: float | None = None
        self._specs: dict[str, dict] = {}
        self._models: dict[str, tuple[nn.Module, list[str], transforms.Compose]] = {}

    def _refresh(self) -> None:
        if not self.registry_path.exists():
            self._specs = {}
            return
        modified = self.registry_path.stat().st_mtime
        if modified == self._registry_mtime:
            return
        registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
        self._specs = registry.get("models", {})
        self._registry_mtime = modified
        self._models.clear()

    def available_crops(self) -> list[str]:
        self._refresh()
        return sorted(self._specs)

    def has_model(self, crop: str) -> bool:
        self._refresh()
        return crop in self._specs

    def _load(self, crop: str) -> tuple[nn.Module, list[str], transforms.Compose]:
        self._refresh()
        if crop in self._models:
            return self._models[crop]
        if crop not in self._specs:
            raise KeyError(f"No registered crop model for {crop}")

        spec = self._specs[crop]
        checkpoint_path = (self.project_root / spec["path"]).resolve()
        if self.project_root not in checkpoint_path.parents:
            raise ValueError("Crop model path must stay inside the project")
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
        class_names = checkpoint["class_names"]
        if checkpoint.get("architecture") != "mobilenet_v3_small":
            raise ValueError(f"Unsupported crop model architecture: {checkpoint.get('architecture')}")
        model = models.mobilenet_v3_small(weights=None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(class_names))
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        image_size = int(checkpoint.get("image_size", 224))
        normalization = checkpoint.get(
            "normalization",
            {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
        )
        transform = transforms.Compose(
            [
                transforms.Resize(256),
                transforms.CenterCrop(image_size),
                transforms.ToTensor(),
                transforms.Normalize(mean=normalization["mean"], std=normalization["std"]),
            ]
        )
        self._models[crop] = (model, class_names, transform)
        return self._models[crop]

    def predict(self, crop: str, image_bytes: bytes) -> Prediction:
        model, class_names, transform = self._load(crop)
        with Image.open(io.BytesIO(image_bytes)) as image:
            batch = transform(image.convert("RGB")).unsqueeze(0)
        with torch.inference_mode():
            probabilities = torch.softmax(model(batch), dim=1)
            confidence, predicted_index = probabilities.max(dim=1)
        return Prediction(class_names[predicted_index.item()], confidence.item())

    def predict_all(self, image_bytes: bytes) -> list[tuple[str, Prediction]]:
        """Run every registered model, isolating a broken checkpoint from the others."""
        predictions: list[tuple[str, Prediction]] = []
        for crop in self.available_crops():
            try:
                predictions.append((f"{crop.replace('_', ' ')} model", self.predict(crop, image_bytes)))
            except Exception:
                logger.exception("Registered crop model failed: %s", crop)
        return predictions
