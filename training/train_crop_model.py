from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms


ROOT = Path(__file__).resolve().parents[1]
PROCESSED_ROOT = ROOT / "data" / "processed"
MODELS_ROOT = ROOT / "Models" / "crops"
REGISTRY_PATH = ROOT / "Models" / "registry.json"
IMAGE_SIZE = 224


def build_model(num_classes: int, pretrained: bool = True) -> nn.Module:
    weights = models.MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, num_classes)
    return model


def build_loaders(data_dir: Path, batch_size: int, workers: int) -> tuple[dict, list[str], Counter]:
    train_transform = transforms.Compose(
        [
            transforms.RandomResizedCrop(IMAGE_SIZE, scale=(0.70, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.RandomRotation(12),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.15),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    evaluation_transform = transforms.Compose(
        [
            transforms.Resize(256),
            transforms.CenterCrop(IMAGE_SIZE),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    split_datasets = {
        "train": datasets.ImageFolder(data_dir / "train", transform=train_transform),
        "val": datasets.ImageFolder(data_dir / "val", transform=evaluation_transform),
        "test": datasets.ImageFolder(data_dir / "test", transform=evaluation_transform),
    }
    class_names = split_datasets["train"].classes
    for split, dataset in split_datasets.items():
        if dataset.classes != class_names:
            raise ValueError(f"Class ordering differs in {split}: {dataset.classes} != {class_names}")
    counts = Counter(split_datasets["train"].targets)
    loaders = {
        split: DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=split == "train",
            num_workers=workers,
            pin_memory=torch.cuda.is_available(),
            persistent_workers=workers > 0,
        )
        for split, dataset in split_datasets.items()
    }
    return loaders, class_names, counts


def class_weights(counts: Counter, class_count: int, device: torch.device) -> torch.Tensor:
    # Square-root inverse weighting controls severe imbalance without over-amplifying rare noise.
    largest = max(counts.values())
    weights = [math.sqrt(largest / max(1, counts[index])) for index in range(class_count)]
    return torch.tensor(weights, dtype=torch.float32, device=device)


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    optimizer: torch.optim.Optimizer | None,
    max_batches: int | None,
) -> tuple[float, float, list[list[int]]]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    correct = 0
    total = 0
    class_count = len(loader.dataset.classes)
    confusion = [[0 for _ in range(class_count)] for _ in range(class_count)]
    scaler = torch.amp.GradScaler("cuda", enabled=training and device.type == "cuda")

    for batch_index, (images, targets) in enumerate(loader):
        if max_batches is not None and batch_index >= max_batches:
            break
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

        predictions = logits.argmax(dim=1)
        total_loss += loss.item() * targets.size(0)
        correct += (predictions == targets).sum().item()
        total += targets.size(0)
        for expected, predicted in zip(targets.cpu().tolist(), predictions.cpu().tolist()):
            confusion[expected][predicted] += 1

    return total_loss / max(1, total), correct / max(1, total), confusion


def macro_f1(confusion: list[list[int]]) -> float:
    scores = []
    for index in range(len(confusion)):
        true_positive = confusion[index][index]
        false_positive = sum(row[index] for row in confusion) - true_positive
        false_negative = sum(confusion[index]) - true_positive
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        scores.append(2 * precision * recall / max(1e-12, precision + recall))
    return sum(scores) / max(1, len(scores))


def update_registry(crop: str, checkpoint_path: Path, class_names: list[str], metrics: dict) -> None:
    registry = {"schema_version": 1, "models": {}}
    if REGISTRY_PATH.exists():
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registry.setdefault("models", {})[crop] = {
        "path": checkpoint_path.relative_to(ROOT).as_posix(),
        "architecture": "mobilenet_v3_small",
        "classes": class_names,
        "image_size": IMAGE_SIZE,
        "test_accuracy": metrics["test_accuracy"],
        "test_macro_f1": metrics["test_macro_f1"],
    }
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a crop-specific Plant AI disease model")
    parser.add_argument("dataset", help="Prepared dataset ID under data/processed")
    parser.add_argument("--crop", required=True, help="Crop name used in the runtime registry")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=24)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--early-stopping-patience", type=int, default=4)
    parser.add_argument("--max-batches", type=int, help="Limit each split for a smoke test")
    parser.add_argument("--register", action="store_true", help="Register the resulting model for Flask")
    args = parser.parse_args()

    random.seed(42)
    torch.manual_seed(42)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data_dir = PROCESSED_ROOT / args.dataset
    loaders, class_names, counts = build_loaders(data_dir, args.batch_size, args.workers)
    if len(class_names) < 2:
        raise SystemExit("Training requires at least two classes")

    model = build_model(len(class_names), pretrained=True).to(device)
    criterion = nn.CrossEntropyLoss(class_weights(counts, len(class_names), device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, args.epochs))
    best_state = None
    best_validation_f1 = -1.0
    history = []
    epochs_without_improvement = 0

    print(f"Device: {device}; classes: {class_names}; train counts: {dict(counts)}", flush=True)
    for epoch in range(1, args.epochs + 1):
        train_loss, train_accuracy, _ = run_epoch(
            model, loaders["train"], criterion, device, optimizer, args.max_batches
        )
        validation_loss, validation_accuracy, validation_confusion = run_epoch(
            model, loaders["val"], criterion, device, None, args.max_batches
        )
        validation_f1 = macro_f1(validation_confusion)
        scheduler.step()
        epoch_metrics = {
            "epoch": epoch,
            "train_loss": train_loss,
            "train_accuracy": train_accuracy,
            "validation_loss": validation_loss,
            "validation_accuracy": validation_accuracy,
            "validation_macro_f1": validation_f1,
        }
        history.append(epoch_metrics)
        print(json.dumps(epoch_metrics), flush=True)
        if validation_f1 > best_validation_f1:
            best_validation_f1 = validation_f1
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.early_stopping_patience:
                print(
                    f"Early stopping after {epoch} epochs without validation macro-F1 improvement.",
                    flush=True,
                )
                break

    if best_state is None:
        raise SystemExit("Training produced no checkpoint")
    model.load_state_dict(best_state)
    model.to(device)
    test_loss, test_accuracy, test_confusion = run_epoch(
        model, loaders["test"], criterion, device, None, args.max_batches
    )
    metrics = {
        "test_loss": test_loss,
        "test_accuracy": test_accuracy,
        "test_macro_f1": macro_f1(test_confusion),
        "confusion_matrix": test_confusion,
        "history": history,
    }

    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    safe_crop = args.crop.lower().replace(" ", "_")
    checkpoint_path = MODELS_ROOT / f"{safe_crop}_mobilenet_v3_small.pth"
    torch.save(
        {
            "state_dict": best_state,
            "architecture": "mobilenet_v3_small",
            "class_names": class_names,
            "crop": args.crop,
            "image_size": IMAGE_SIZE,
            "normalization": {
                "mean": [0.485, 0.456, 0.406],
                "std": [0.229, 0.224, 0.225],
            },
            "dataset": args.dataset,
            "metrics": metrics,
        },
        checkpoint_path,
    )
    checkpoint_path.with_suffix(".metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )
    if args.register and args.max_batches is None:
        update_registry(args.crop, checkpoint_path, class_names, metrics)
    elif args.register:
        print("Smoke-test checkpoints are not registered for production inference.")
    print(f"Saved checkpoint: {checkpoint_path}")
    print(json.dumps({key: metrics[key] for key in ("test_loss", "test_accuracy", "test_macro_f1")}))


if __name__ == "__main__":
    main()
