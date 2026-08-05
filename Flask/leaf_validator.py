from __future__ import annotations

from dataclasses import dataclass
import io
import os
from threading import Lock

import open_clip
import torch
from PIL import Image


PLANT_LEAF_PROMPTS = [
    "a close-up photograph of a real plant leaf",
    "a photograph of a diseased crop leaf",
    "a photograph of a healthy crop leaf",
    "a plant leaf showing spots or discoloration",
    "green leaves attached to a crop plant",
    "the upper or lower surface of a living leaf",
]

NON_LEAF_PROMPTS = [
    "a photograph of a car, truck, bus, or motorcycle",
    "a photograph of a person",
    "a photograph of an animal",
    "a photograph of a building or an indoor room",
    "a photograph of food on a plate",
    "a photograph of an electronic device",
    "a screenshot, document, drawing, or diagram",
    "a photograph of a household object or machine",
    "a landscape without a close-up plant leaf",
    "a blurry image with no identifiable plant leaf",
]


@dataclass(frozen=True)
class LeafValidation:
    is_leaf: bool
    confidence: float


class LeafValidator:
    """Zero-shot leaf gate that runs before disease classification."""

    def __init__(self) -> None:
        self.model_name = os.getenv("LEAF_VALIDATOR_MODEL", "ViT-B-32-quickgelu")
        self.pretrained = os.getenv("LEAF_VALIDATOR_WEIGHTS", "openai")
        self.threshold = float(os.getenv("LEAF_VALIDATOR_THRESHOLD", "0.60"))
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = None
        self._preprocess = None
        self._text_features = None
        self._lock = Lock()

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            model, _, preprocess = open_clip.create_model_and_transforms(
                self.model_name,
                pretrained=self.pretrained,
                device=self.device,
            )
            model.eval()
            tokenizer = open_clip.get_tokenizer(self.model_name)
            prompts = PLANT_LEAF_PROMPTS + NON_LEAF_PROMPTS
            tokens = tokenizer(prompts).to(self.device)
            with torch.inference_mode():
                text_features = model.encode_text(tokens)
                text_features /= text_features.norm(dim=-1, keepdim=True)
            self._model = model
            self._preprocess = preprocess
            self._text_features = text_features

    def validate(self, image_bytes: bytes) -> LeafValidation:
        self._load()
        image_features = self._encode_image(image_bytes)
        with torch.inference_mode():
            similarities = image_features @ self._text_features.T
            plant_score = similarities[:, : len(PLANT_LEAF_PROMPTS)].mean(dim=1)
            non_leaf_score = similarities[:, len(PLANT_LEAF_PROMPTS) :].mean(dim=1)
            confidence = torch.softmax(
                torch.stack([plant_score, non_leaf_score], dim=1) * 100.0,
                dim=1,
            )[0, 0].item()
        return LeafValidation(is_leaf=confidence >= self.threshold, confidence=confidence)

    def _encode_image(self, image_bytes: bytes) -> torch.Tensor:
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_tensor = self._preprocess(image.convert("RGB")).unsqueeze(0).to(self.device)
        with torch.inference_mode():
            image_features = self._model.encode_image(image_tensor)
            image_features /= image_features.norm(dim=-1, keepdim=True)
        return image_features

    def crop_probabilities(self, image_bytes: bytes, crop_names: list[str]) -> dict[str, float]:
        """Return relative zero-shot crop matches for cross-model routing."""
        unique_crops = list(dict.fromkeys(crop_names))
        if not unique_crops:
            return {}
        if len(unique_crops) == 1:
            return {unique_crops[0]: 1.0}
        self._load()
        tokenizer = open_clip.get_tokenizer(self.model_name)
        prompts = [f"a close-up photograph of a real {crop} crop leaf" for crop in unique_crops]
        tokens = tokenizer(prompts).to(self.device)
        with torch.inference_mode():
            text_features = self._model.encode_text(tokens)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            image_features = self._encode_image(image_bytes)
            probabilities = torch.softmax(100.0 * image_features @ text_features.T, dim=1)[0]
        return {crop: probabilities[index].item() for index, crop in enumerate(unique_crops)}

    def warm_up(self) -> None:
        self._load()
