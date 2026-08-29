"""Render a narrated, judge-facing Plant AI overview video."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

import imageio.v2 as imageio
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "competition" / "plant-ai-demo.mp4"

SLIDES = [
    (
        "Plant AI",
        "Field Triage Agent",
        "A reviewable first screen for plant-leaf photos\nAgent branch · evidence-grounded · human-controlled",
        "Plant AI helps a grower or extension officer turn a plant-leaf photo into a fast, reviewable first triage. This video covers the product, agent workflow, safety controls, evidence, measured improvement, and reproducibility.",
    ),
    (
        "01  Scan the right evidence",
        "Leaf-only intake",
        "Upload a leaf photo · add crop and symptoms · scan every registered model\nCars, documents, and unrelated images stop at the leaf gate.",
        "The scan starts with a validated image and optional context: reported crop, location, symptoms, duration, and recent treatment. The OpenCLIP leaf gate rejects unrelated images before disease classification. Plant AI then compares the original classifier and all registered crop models automatically.",
    ),
    (
        "02  Uncertainty is a route",
        "Clarify before diagnosing",
        "Low confidence → ask only for missing critical context\nNo diagnosis · no treatment advice · no allowance consumed",
        "When local model evidence is weak, the intake agent asks only for the missing crop or symptom information. A clarification result is not a diagnosis and does not spend an anonymous or free-account scan allowance. If an analysis tool fails, the workflow escalates safely to a plant professional or laboratory.",
    ),
    (
        "03  Evidence-backed guidance",
        "Approved sources, exact scope",
        "Versioned university extension and UC IPM corpus\nClaim-level source links · regional limits · unsupported crops fall back safely",
        "Management actions come only from a reviewed, hashed local corpus of university extension and integrated pest management guidance. Each action carries a source link and regional scope. If the predicted crop and condition are unsupported, Plant AI omits condition-specific treatment advice instead of inventing it.",
    ),
    (
        "04  Human approval stays in control",
        "Verification checkpoint",
        "Confidence · model agreement · evidence availability\nEvery completed report remains pending human confirmation before treatment",
        "After retrieval, the verification node checks confidence, cross-model crop disagreement, and evidence availability. The report shows a pending human checkpoint and explains why review is needed. Plant AI never selects a pesticide, dosage, or application schedule, and it never presents an image-only result as a confirmed diagnosis.",
    ),
    (
        "05  Measured, reproducible progress",
        "Evidence-aware v2 comparison",
        "Correct-and-safe: 4/13 → 5/13\nUnsupported management violations: 6 → 2\nCrop and condition accuracy: 44.4% (unchanged)",
        "On the same thirteen image assets and labels, evidence-aware retrieval improved correct-and-safe triage from four of thirteen to five of thirteen and reduced unsupported management violations from six to two. Crop and condition accuracy stayed at forty-four point four percent, so this is an evidence-safety gain, not a vision-accuracy claim.",
    ),
    (
        "06  Reproduce it",
        "Clean clone, no private credentials",
        "python scripts\\smoke_test.py\n61 tests passing · offline evaluation · zero external API cost\nagent branch · demo script · rubric audit · trajectories",
        "The project includes a Python three point eleven lock snapshot, a secret-free in-memory SQLite smoke test, reproducibility instructions, evaluation manifests, and sanitized trajectories for success, rejection, clarification, retry, and safe failure. The final submission package is documented in the repository. Thank you.",
    ),
]


def font(size: int, bold: bool = False):
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def render_slide(title: str, subtitle: str, body: str, index: int) -> Image.Image:
    image = Image.new("RGB", (1920, 1080), (247, 244, 235))
    draw = ImageDraw.Draw(image)
    green = (25, 57, 45)
    accent = (126, 154, 91)
    muted = (91, 100, 91)
    draw.rectangle((0, 0, 1920, 18), fill=accent)
    draw.ellipse((1480, -260, 2130, 390), fill=(226, 235, 214))
    draw.ellipse((1640, 760, 2110, 1230), fill=(236, 229, 211))
    draw.text((130, 110), f"PLANT AI  /  {index:02d}", font=font(27, True), fill=accent)
    draw.text((130, 205), title, font=font(72, True), fill=green)
    draw.text((130, 330), subtitle, font=font(44, True), fill=green)
    y = 500
    for line in body.split("\n"):
        draw.text((145, y), line, font=font(37), fill=muted)
        y += 66
    draw.line((130, 900, 1790, 900), fill=(207, 211, 199), width=2)
    draw.text((130, 935), "Preliminary screening · confirm locally before treatment", font=font(25), fill=muted)
    draw.text((1570, 935), "agent branch", font=font(25, True), fill=green)
    return image


def make_audio(text: str, output: Path) -> None:
    text_file = output.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate=0; $s.Volume=100; "
        "$s.SetOutputToWaveFile([Environment]::GetEnvironmentVariable('PLANT_AI_AUDIO')); "
        "$s.Speak((Get-Content -Raw -LiteralPath ([Environment]::GetEnvironmentVariable('PLANT_AI_SCRIPT')))); "
        "$s.Dispose()"
    )
    env = dict(**__import__("os").environ, PLANT_AI_AUDIO=str(output), PLANT_AI_SCRIPT=str(text_file))
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, env=env)
    text_file.unlink(missing_ok=True)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="plant-ai-demo-") as temp_name:
        temp = Path(temp_name)
        video_only = temp / "video.mp4"
        audio = temp / "narration.wav"
        writer = imageio.get_writer(
            str(video_only), fps=30, codec="libx264", quality=7, macro_block_size=1,
        )
        try:
            for index, (title, subtitle, body, _) in enumerate(SLIDES, start=1):
                frame = render_slide(title, subtitle, body, index)
                # Hold each chapter long enough for narration and readable text.
                duration = 25 if index != len(SLIDES) else 30
                for _ in range(duration * 30):
                    writer.append_data(__import__("numpy").asarray(frame))
        finally:
            writer.close()
        make_audio(" ".join(item[3] for item in SLIDES), audio)
        ffmpeg = get_ffmpeg_exe()
        subprocess.run(
            [ffmpeg, "-y", "-i", str(video_only), "-i", str(audio), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(OUTPUT)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
