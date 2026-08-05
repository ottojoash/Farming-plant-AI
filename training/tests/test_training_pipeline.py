from __future__ import annotations

import io
import zipfile

from PIL import Image

from training import prepare_dataset
from training.train_crop_model import macro_f1


def jpeg_bytes(color: tuple[int, int, int]) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 32), color).save(output, format="JPEG")
    return output.getvalue()


def test_split_is_deterministic_and_grouped():
    digest = "ab" * 32

    assert prepare_dataset.choose_split(digest) == prepare_dataset.choose_split(digest)
    assert prepare_dataset.choose_split(digest) in {"train", "val", "test"}


def test_neighboring_sequence_frames_share_a_split():
    first = prepare_dataset.member_group_digest("anthra/anthra1201.jpg", "a" * 64)
    second = prepare_dataset.member_group_digest("anthra/anthra1299.jpg", "b" * 64)

    assert first == second
    assert prepare_dataset.choose_split(first) == prepare_dataset.choose_split(second)


def test_repository_zip_normalizes_labels_and_preserves_source_test(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    processed_root = tmp_path / "processed"
    monkeypatch.setattr(prepare_dataset, "RAW_ROOT", raw_root)
    monkeypatch.setattr(prepare_dataset, "PROCESSED_ROOT", processed_root)
    archive_path = raw_root / "sample" / "archives" / "sample.zip"
    archive_path.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("repo/train/Source Leaf/train.jpg", jpeg_bytes((10, 180, 20)))
        archive.writestr("repo/train/Source Leaf/train-2.jpg", jpeg_bytes((15, 170, 25)))
        archive.writestr("repo/test/Source Leaf/test.jpg", jpeg_bytes((20, 160, 30)))
        archive.writestr("repo/test/Source Leaf/duplicate.jpg", jpeg_bytes((20, 160, 30)))

    summary = prepare_dataset.prepare_repository_zip(
        "sample",
        {
            "archive": "sample.zip",
            "label_aliases": {"Source Leaf": "Crop___healthy"},
        },
        max_per_class=None,
    )

    assert summary["counts"] == {"Crop___healthy": 3}
    assert summary["duplicates_skipped"] == 1
    assert len(list((processed_root / "sample" / "test" / "Crop___healthy").glob("*.jpg"))) == 1


def test_macro_f1_for_perfect_confusion_matrix():
    assert macro_f1([[3, 0], [0, 4]]) == 1.0
