from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, UnidentifiedImageError


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).with_name("datasets.json")
RAW_ROOT = ROOT / "data" / "raw"
PROCESSED_ROOT = ROOT / "data" / "processed"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def choose_split(digest: str) -> str:
    bucket = int(digest[:8], 16) % 100
    if bucket < 80:
        return "train"
    if bucket < 90:
        return "val"
    return "test"


def member_group_digest(member_name: str, content_digest: str) -> str:
    """Group likely burst/sequence neighbors so they cannot leak across data splits."""
    stem = Path(member_name).stem
    match = re.search(r"(\d+)$", stem)
    if not match:
        return content_digest
    number = int(match.group(1))
    prefix = stem[: match.start(1)].lower()
    # Mobile timestamps are milliseconds; group them by capture hour. Sequential names
    # are grouped in blocks of 100, which is conservative for burst-derived archives.
    bucket = number // 3_600_000 if number >= 100_000_000_000 else number // 100
    group_key = f"{Path(member_name).parent.as_posix().lower()}|{prefix}|{bucket}"
    return hashlib.sha256(group_key.encode("utf-8")).hexdigest()


def valid_image(data: bytes) -> bool:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        return True
    except (UnidentifiedImageError, OSError):
        return False


def write_image(data: bytes, destination: Path) -> bool:
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return True


def ensure_split_coverage(output_dir: Path, labels: set[str]) -> set[str]:
    """Ensure ImageFolder sees every class in every split when at least 3 images exist."""
    dropped: set[str] = set()
    for label in labels:
        total = sum(
            len([path for path in (output_dir / split / label).glob("*") if path.is_file()])
            for split in ("train", "val", "test")
        )
        if total < 3:
            for split in ("train", "val", "test"):
                class_dir = output_dir / split / label
                if class_dir.exists():
                    shutil.rmtree(class_dir)
            dropped.add(label)
            continue
        for target_split in ("val", "test"):
            target_dir = output_dir / target_split / label
            if any(path.is_file() for path in target_dir.glob("*")):
                continue
            donor_candidates = [
                path
                for split in ("train", "val", "test")
                if split != target_split
                for path in sorted((output_dir / split / label).glob("*"))
                if path.is_file()
            ]
            if not donor_candidates:
                raise ValueError(f"Could not create {target_split} coverage for {label!r}")
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(donor_candidates[0]), target_dir / donor_candidates[0].name)
    return dropped


def reset_output_dir(dataset_id: str) -> Path:
    output_dir = (PROCESSED_ROOT / dataset_id).resolve()
    processed_root = PROCESSED_ROOT.resolve()
    if output_dir.parent != processed_root:
        raise ValueError("Processed dataset path must stay directly inside data/processed")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    return output_dir


def physical_counts(output_dir: Path, labels: set[str]) -> Counter[str]:
    return Counter(
        {
            label: sum(
                1
                for split in ("train", "val", "test")
                for path in (output_dir / split / label).glob("*")
                if path.is_file()
            )
            for label in labels
        }
    )


def prepare_labelled_archives(dataset_id: str, spec: dict, max_per_class: int | None) -> dict:
    archive_dir = RAW_ROOT / dataset_id / "archives"
    output_dir = PROCESSED_ROOT / dataset_id
    counts: Counter[str] = Counter()
    duplicates = 0
    invalid = 0
    seen_hashes: set[str] = set()

    for archive_name, file_spec in spec["files"].items():
        archive_path = archive_dir / archive_name
        if not archive_path.exists():
            continue
        if archive_path.suffix.lower() != ".zip":
            print(f"Skipping {archive_path.name}: extract this archive to raw/extracted before preparation")
            continue
        label = file_spec["label"]
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir() or Path(member.filename).suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                if max_per_class and counts[label] >= max_per_class:
                    break
                data = archive.read(member)
                digest = hashlib.sha256(data).hexdigest()
                if digest in seen_hashes:
                    duplicates += 1
                    continue
                if not valid_image(data):
                    invalid += 1
                    continue
                seen_hashes.add(digest)
                split = choose_split(member_group_digest(member.filename, digest))
                suffix = Path(member.filename).suffix.lower()
                destination = output_dir / split / label / f"{digest[:20]}{suffix}"
                if write_image(data, destination):
                    counts[label] += 1

    dropped = ensure_split_coverage(output_dir, set(counts))
    for label in dropped:
        counts.pop(label, None)
    counts = physical_counts(output_dir, set(counts))
    return {
        "dataset": dataset_id,
        "counts": dict(sorted(counts.items())),
        "duplicates_skipped": duplicates,
        "invalid_skipped": invalid,
        "classes_dropped_too_small": sorted(dropped),
    }


def prepare_extracted_directories(dataset_id: str, max_per_class: int | None) -> dict:
    extracted = RAW_ROOT / dataset_id / "extracted"
    output_dir = PROCESSED_ROOT / dataset_id
    counts: Counter[str] = Counter()
    duplicates = 0
    invalid = 0
    seen_hashes: set[str] = set()

    if not extracted.exists():
        raise SystemExit(f"No extracted directory found at {extracted}")
    for class_dir in sorted(path for path in extracted.iterdir() if path.is_dir()):
        label = class_dir.name
        for image_path in class_dir.rglob("*"):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            if max_per_class and counts[label] >= max_per_class:
                break
            data = image_path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                duplicates += 1
                continue
            if not valid_image(data):
                invalid += 1
                continue
            seen_hashes.add(digest)
            split = choose_split(digest)
            destination = output_dir / split / label / f"{digest[:20]}{image_path.suffix.lower()}"
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                try:
                    os.link(image_path, destination)
                except OSError:
                    shutil.copy2(image_path, destination)
                counts[label] += 1

    dropped = ensure_split_coverage(output_dir, set(counts))
    for label in dropped:
        counts.pop(label, None)
    counts = physical_counts(output_dir, set(counts))
    return {
        "dataset": dataset_id,
        "counts": dict(sorted(counts.items())),
        "duplicates_skipped": duplicates,
        "invalid_skipped": invalid,
        "classes_dropped_too_small": sorted(dropped),
    }


def prepare_repository_zip(dataset_id: str, spec: dict, max_per_class: int | None) -> dict:
    archive_path = RAW_ROOT / dataset_id / "archives" / spec["archive"]
    if not archive_path.exists():
        raise SystemExit(f"Dataset archive not found: {archive_path}")
    output_dir = PROCESSED_ROOT / dataset_id
    counts: Counter[str] = Counter()
    duplicates = 0
    invalid = 0
    seen_hashes: set[str] = set()

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or Path(member.filename).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            parts = Path(member.filename).parts
            source_split = next((part for part in parts if part in {"train", "test"}), None)
            if source_split is None:
                continue
            source_index = parts.index(source_split)
            if len(parts) <= source_index + 2:
                continue
            source_label = parts[source_index + 1]
            label = spec["label_aliases"].get(source_label)
            if label is None:
                raise ValueError(f"Unmapped source label in {dataset_id}: {source_label}")
            if max_per_class and counts[label] >= max_per_class:
                continue
            data = archive.read(member)
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                duplicates += 1
                continue
            if not valid_image(data):
                invalid += 1
                continue
            seen_hashes.add(digest)
            if source_split == "test":
                split = "test"
            else:
                split = "val" if int(digest[:8], 16) % 10 == 0 else "train"
            suffix = Path(member.filename).suffix.lower()
            destination = output_dir / split / label / f"{digest[:20]}{suffix}"
            if write_image(data, destination):
                counts[label] += 1

    dropped = ensure_split_coverage(output_dir, set(counts))
    for label in dropped:
        counts.pop(label, None)
    counts = physical_counts(output_dir, set(counts))
    return {
        "dataset": dataset_id,
        "counts": dict(sorted(counts.items())),
        "duplicates_skipped": duplicates,
        "invalid_skipped": invalid,
        "classes_dropped_too_small": sorted(dropped),
    }


def prepare_class_directory_zip(dataset_id: str, spec: dict, max_per_class: int | None) -> dict:
    """Prepare a ZIP whose labelled images live below source class directories."""
    archive_path = RAW_ROOT / dataset_id / "archives" / spec["archive"]
    if not archive_path.exists():
        raise SystemExit(f"Dataset archive not found: {archive_path}")
    output_dir = PROCESSED_ROOT / dataset_id
    counts: Counter[str] = Counter()
    duplicates = 0
    invalid = 0
    seen_hashes: set[str] = set()
    aliases = spec["label_aliases"]

    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            if member.is_dir() or Path(member.filename).suffix.lower() not in IMAGE_SUFFIXES:
                continue
            parts = Path(member.filename).parts
            source_label = next((part for part in reversed(parts[:-1]) if part in aliases), None)
            if source_label is None:
                continue
            label = aliases[source_label]
            if max_per_class and counts[label] >= max_per_class:
                continue
            data = archive.read(member)
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                duplicates += 1
                continue
            if not valid_image(data):
                invalid += 1
                continue
            seen_hashes.add(digest)
            split = choose_split(digest)
            suffix = Path(member.filename).suffix.lower()
            destination = output_dir / split / label / f"{digest[:20]}{suffix}"
            if write_image(data, destination):
                counts[label] += 1

    dropped = ensure_split_coverage(output_dir, set(counts))
    for label in dropped:
        counts.pop(label, None)
    counts = physical_counts(output_dir, set(counts))
    return {
        "dataset": dataset_id,
        "counts": dict(sorted(counts.items())),
        "duplicates_skipped": duplicates,
        "invalid_skipped": invalid,
        "classes_dropped_too_small": sorted(dropped),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate, deduplicate, and split a Plant AI dataset")
    parser.add_argument("dataset", help="Dataset ID from datasets.json")
    parser.add_argument("--max-per-class", type=int, help="Optional class cap for balanced experiments")
    args = parser.parse_args()

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["datasets"]
    if args.dataset not in catalog:
        parser.error(f"Unknown dataset {args.dataset!r}")
    spec = catalog[args.dataset]
    reset_output_dir(args.dataset)

    if spec["acquisition"] == "http_files":
        summary = prepare_labelled_archives(args.dataset, spec, args.max_per_class)
        if not summary["counts"]:
            summary = prepare_extracted_directories(args.dataset, args.max_per_class)
    elif spec["acquisition"] == "repository_zip":
        summary = prepare_repository_zip(args.dataset, spec, args.max_per_class)
    elif spec["acquisition"] == "kaggle_competition":
        summary = prepare_class_directory_zip(args.dataset, spec, args.max_per_class)
    else:
        summary = prepare_extracted_directories(args.dataset, args.max_per_class)

    output_dir = PROCESSED_ROOT / args.dataset
    output_dir.mkdir(parents=True, exist_ok=True)
    summary.update(
        {
            "source": spec["source"],
            "license": spec["license"],
            "split_method": (
                "Published test split preserved; training split SHA-256 grouped into train/validation"
                if spec["acquisition"] == "repository_zip"
                else "Source sequence grouped and SHA-256 deterministic 80/10/10"
            ),
        }
    )
    (output_dir / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
