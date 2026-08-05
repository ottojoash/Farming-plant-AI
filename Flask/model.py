from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import io

import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR.parent / "Models" / "plantDisease-resnet34.pth"

NUM_CLASSES = [
    "Apple___Apple_scab", "Apple___Black_rot", "Apple___Cedar_apple_rust", "Apple___healthy",
    "Blueberry___healthy", "Cherry_(including_sour)___Powdery_mildew",
    "Cherry_(including_sour)___healthy", "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot",
    "Corn_(maize)___Common_rust_", "Corn_(maize)___Northern_Leaf_Blight",
    "Corn_(maize)___healthy", "Grape___Black_rot", "Grape___Esca_(Black_Measles)",
    "Grape___Leaf_blight_(Isariopsis_Leaf_Spot)", "Grape___healthy",
    "Orange___Haunglongbing_(Citrus_greening)", "Peach___Bacterial_spot", "Peach___healthy",
    "Pepper,_bell___Bacterial_spot", "Pepper,_bell___healthy", "Potato___Early_blight",
    "Potato___Late_blight", "Potato___healthy", "Raspberry___healthy", "Soybean___healthy",
    "Squash___Powdery_mildew", "Strawberry___Leaf_scorch", "Strawberry___healthy",
    "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
    "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite", "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
]


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float


class PlantDiseaseModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        # The checkpoint already contains all weights, so no network download is needed.
        self.network = models.resnet34(weights=None)
        self.network.fc = nn.Linear(self.network.fc.in_features, len(NUM_CLASSES))

    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        return self.network(batch)


TRANSFORM = transforms.Compose(
    [
        transforms.Resize(size=128),
        transforms.ToTensor(),
    ]
)

model = PlantDiseaseModel()
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu", weights_only=True))
model.eval()


def predict_image(image_bytes: bytes) -> Prediction:
    with Image.open(io.BytesIO(image_bytes)) as image:
        tensor = TRANSFORM(image.convert("RGB"))

    batch = tensor.unsqueeze(0)
    with torch.inference_mode():
        probabilities = torch.softmax(model(batch), dim=1)
        confidence, predicted_index = probabilities.max(dim=1)

    return Prediction(
        label=NUM_CLASSES[predicted_index.item()],
        confidence=confidence.item(),
    )
