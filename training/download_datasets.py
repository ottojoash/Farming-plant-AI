from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path(__file__).with_name("datasets.json")
RAW_ROOT = ROOT / "data" / "raw"


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["datasets"]


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "Plant-AI-dataset-manager/1.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        append = existing > 0 and response.status == 206
        mode = "ab" if append else "wb"
        if not append:
            existing = 0
        total = response.headers.get("Content-Length")
        expected = existing + int(total) if total else None
        downloaded = existing
        with partial.open(mode) as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                downloaded += len(chunk)
                if expected:
                    print(
                        f"\r{destination.name}: {downloaded / 1024**3:.2f}/{expected / 1024**3:.2f} GB",
                        end="",
                        flush=True,
                    )
    print()
    partial.replace(destination)


def download_http_dataset(name: str, spec: dict, selected_files: list[str]) -> None:
    destination = RAW_ROOT / name / "archives"
    for filename in selected_files:
        if filename not in spec["files"]:
            raise SystemExit(f"Unknown file {filename!r} for dataset {name}")
        file_spec = spec["files"][filename]
        target = destination / filename
        if target.exists():
            if checksum := file_spec.get("md5"):
                if file_digest(target, "md5") != checksum:
                    raise SystemExit(f"Checksum mismatch for existing file: {target}")
            print(f"Already downloaded: {target}")
            continue
        download_file(file_spec["url"], target)
        if checksum := file_spec.get("md5"):
            actual = file_digest(target, "md5")
            if actual != checksum:
                raise SystemExit(f"Checksum mismatch for {target}: expected {checksum}, got {actual}")


def clone_git_dataset(name: str, spec: dict) -> None:
    destination = RAW_ROOT / name / "repository"
    if (destination / ".git").exists():
        print(f"Already cloned: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", spec["repository"], str(destination)],
        check=True,
    )


def download_kaggle_dataset(name: str, spec: dict) -> None:
    kaggle = shutil.which("kaggle")
    if not kaggle:
        raise SystemExit(
            "The Kaggle CLI is not installed. Install it, configure kaggle.json, accept the "
            f"{spec['competition']} competition rules, then run this command again."
        )
    destination = RAW_ROOT / name / "archives"
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [kaggle, "competitions", "download", "-c", spec["competition"], "-p", str(destination)],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Download provenance-tracked Plant AI datasets")
    parser.add_argument("dataset", nargs="?", help="Dataset ID from datasets.json")
    parser.add_argument("--list", action="store_true", help="List available datasets")
    parser.add_argument("--all-files", action="store_true", help="Download every file for an HTTP dataset")
    parser.add_argument("--files", nargs="*", help="Download only these archive names")
    args = parser.parse_args()

    catalog = load_catalog()
    if args.list:
        for dataset_id, spec in catalog.items():
            print(f"{dataset_id:20} {spec['crop']:12} {spec['title']}")
        return
    if not args.dataset or args.dataset not in catalog:
        parser.error("Provide a valid dataset ID or use --list")

    spec = catalog[args.dataset]
    print(f"Dataset: {spec['title']}\nSource: {spec['source']}\nLicense: {spec['license']}")
    acquisition = spec["acquisition"]
    if acquisition == "http_files":
        selected = args.files or (list(spec["files"]) if args.all_files else spec["starter_files"])
        download_http_dataset(args.dataset, spec, selected)
    elif acquisition == "git":
        clone_git_dataset(args.dataset, spec)
    elif acquisition == "repository_zip":
        target = RAW_ROOT / args.dataset / "archives" / spec["archive"]
        if target.exists():
            print(f"Already downloaded: {target}")
        else:
            download_file(spec["url"], target)
    elif acquisition == "kaggle_competition":
        download_kaggle_dataset(args.dataset, spec)
    else:
        raise SystemExit(f"Unsupported acquisition method: {acquisition}")


if __name__ == "__main__":
    main()
