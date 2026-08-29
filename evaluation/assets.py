from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


GENERATOR_VERSION = 1


class AssetError(RuntimeError):
    """Raised when an evaluation asset is missing or has changed."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pixel_sha256(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    header = f"RGB:{rgb.width}x{rgb.height}:".encode("ascii")
    return sha256_bytes(header + rgb.tobytes())


def _vehicle_control() -> Image.Image:
    image = Image.new("RGB", (512, 384), (185, 215, 238))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 270, 512, 384), fill=(70, 74, 80))
    draw.rectangle((118, 188, 397, 286), fill=(205, 36, 45))
    draw.polygon([(180, 188), (232, 130), (333, 130), (374, 188)], fill=(180, 30, 38))
    draw.polygon([(199, 179), (239, 141), (278, 141), (278, 179)], fill=(205, 230, 242))
    draw.polygon([(288, 141), (327, 141), (356, 179), (288, 179)], fill=(205, 230, 242))
    draw.ellipse((153, 255, 218, 320), fill=(25, 25, 28))
    draw.ellipse((314, 255, 379, 320), fill=(25, 25, 28))
    draw.ellipse((170, 272, 201, 303), fill=(145, 150, 158))
    draw.ellipse((331, 272, 362, 303), fill=(145, 150, 158))
    return image


def _document_control() -> Image.Image:
    image = Image.new("RGB", (512, 384), (224, 226, 230))
    draw = ImageDraw.Draw(image)
    draw.rectangle((105, 30, 407, 354), fill=(255, 255, 250), outline=(80, 84, 90), width=3)
    draw.rectangle((145, 76, 315, 94), fill=(45, 50, 58))
    for y, width in [(125, 218), (158, 205), (191, 230), (224, 180), (277, 225), (310, 150)]:
        draw.rectangle((145, y, 145 + width, y + 8), fill=(110, 116, 125))
    return image


def _leaf_art_control() -> Image.Image:
    image = Image.new("RGB", (512, 384), (250, 247, 238))
    draw = ImageDraw.Draw(image)
    draw.line((256, 330, 256, 118), fill=(65, 95, 44), width=12)
    draw.ellipse((95, 62, 287, 220), fill=(76, 170, 78), outline=(32, 99, 48), width=6)
    draw.ellipse((225, 105, 420, 270), fill=(91, 185, 83), outline=(32, 99, 48), width=6)
    draw.line((256, 140, 165, 112), fill=(45, 118, 55), width=5)
    draw.line((258, 183, 347, 160), fill=(45, 118, 55), width=5)
    return image


GENERATORS = {
    "geometric_vehicle": _vehicle_control,
    "document_page": _document_control,
    "leaf_drawing": _leaf_art_control,
}


def _encode_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False, compress_level=9)
    return output.getvalue()


def generated_asset(spec: dict[str, Any]) -> tuple[bytes, str]:
    if int(spec.get("generator_version", 0)) != GENERATOR_VERSION:
        raise AssetError(f"Unsupported generator version: {spec.get('generator_version')}")
    name = spec.get("generator")
    if name not in GENERATORS:
        raise AssetError(f"Unknown deterministic generator: {name}")
    image = GENERATORS[name]()
    return _encode_png(image), pixel_sha256(image)


def _file_asset(spec: dict[str, Any], project_root: Path) -> tuple[bytes, str]:
    path = (project_root / spec["path"]).resolve()
    if project_root.resolve() not in path.parents:
        raise AssetError(f"Asset path leaves the repository: {spec['path']}")
    if not path.is_file():
        dataset = spec.get("dataset", "required dataset")
        raise AssetError(
            f"Missing {spec['path']}. Acquire and prepare {dataset} as described in evaluation/README.md."
        )
    data = path.read_bytes()
    actual = sha256_bytes(data)
    if actual != spec["sha256"]:
        raise AssetError(f"SHA-256 mismatch for {spec['path']}: expected {spec['sha256']}, got {actual}")
    return data, actual


def materialize_asset(spec: dict[str, Any], project_root: Path) -> tuple[bytes, str]:
    kind = spec.get("kind")
    if kind == "file":
        return _file_asset(spec, project_root)
    if kind == "generated":
        data, actual = generated_asset(spec)
        if actual != spec["pixel_sha256"]:
            raise AssetError(
                f"Generated pixel hash mismatch for {spec.get('generator')}: "
                f"expected {spec['pixel_sha256']}, got {actual}"
            )
        return data, actual
    if kind == "blurred_file":
        source_data, _ = _file_asset(spec["source"], project_root)
        with Image.open(io.BytesIO(source_data)) as source:
            image = source.convert("RGB")
            image.thumbnail((96, 96))
            image = image.resize((512, 384)).filter(ImageFilter.GaussianBlur(radius=float(spec["radius"])))
        actual = pixel_sha256(image)
        if actual != spec["pixel_sha256"]:
            raise AssetError(
                f"Blurred pixel hash mismatch: expected {spec['pixel_sha256']}, got {actual}"
            )
        return _encode_png(image), actual
    raise AssetError(f"Unsupported asset kind: {kind}")
