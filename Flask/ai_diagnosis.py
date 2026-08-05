from __future__ import annotations

import base64
import os

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class AIDiagnosis(BaseModel):
    """A cautious, image-based plant health assessment."""

    plant_name: str = Field(description="Likely common plant name, or Unknown")
    likely_condition: str = Field(description="Likely disease, pest, deficiency, damage, healthy, or Unknown")
    confidence_level: str = Field(description="One of: low, medium, high")
    summary: str = Field(description="Short plain-language assessment")
    visible_observations: list[str] = Field(description="Only symptoms that are visible in the image")
    possible_causes: list[str] = Field(description="Plausible causes, clearly phrased as possibilities")
    recommended_next_steps: list[str] = Field(description="Low-risk observation, isolation, sanitation, or expert-help steps")
    uncertainty_note: str = Field(description="What cannot be confirmed from this image and when expert or lab help is needed")


SYSTEM_PROMPT = """
You are the cautious vision fallback for Plant AI. Examine the supplied plant image.
The local classifier was uncertain or does not support this plant or condition.

Rules:
- Never claim that an image-only assessment is a confirmed diagnosis.
- If the image is not a plant, is too unclear, or lacks useful symptoms, say Unknown.
- Separate visible observations from possible causes.
- Consider disease, pests, nutrient problems, water stress, physical damage, and a healthy plant.
- Do not invent details that are not visible.
- Do not recommend pesticide product names, application rates, or dosages.
- Prefer low-risk next steps and recommend local extension or laboratory confirmation when appropriate.
- Keep every list concise and useful to a farmer.
""".strip()


def is_ai_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def diagnose_with_ai(image_bytes: bytes, mime_type: str) -> AIDiagnosis:
    if not is_ai_available():
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model = ChatOpenAI(
        model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.6-sol"),
        reasoning_effort=os.getenv("OPENAI_REASONING_EFFORT", "low"),
        timeout=45,
        max_retries=1,
        use_responses_api=True,
    )
    structured_model = model.with_structured_output(AIDiagnosis, method="json_schema")
    encoded_image = base64.b64encode(image_bytes).decode("ascii")

    return structured_model.invoke(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Provide a cautious plant-health assessment for this image.",
                    },
                    {
                        "type": "image",
                        "base64": encoded_image,
                        "mime_type": mime_type,
                    },
                ],
            },
        ]
    )
