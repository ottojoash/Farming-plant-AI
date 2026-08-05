# Plant AI dataset guide

Plant AI keeps dataset acquisition separate from application source code. Raw files live in
`data/raw/`, validated splits in `data/processed/`, and trained crop checkpoints in
`Models/crops/`. These large/generated paths are ignored by Git.

## Catalogued datasets

| ID | Crop/role | Acquisition | Notes |
|---|---|---|---|
| `beans_tanzania` | Bean anthracnose, rust, healthy | Direct Zenodo archives | Starter set uses the three labelled archives listed in `training/datasets.json`. |
| `cassava_makerere` | Cassava diseases and healthy leaves | Direct archives | Some files are RAR archives and must be extracted into `data/raw/cassava_makerere/extracted/<class>/`. |
| `paddy_doctor` | Rice/paddy diseases and healthy leaves | Kaggle CLI | Accept the competition terms and configure Kaggle credentials first. |
| `plantdoc` | Field-image robustness across many crops | GitHub repository ZIP | Useful for robustness experiments; labels are normalized by the catalogue. |

The catalogue records source URLs, citations, checksums where published, class aliases, and
license/terms notes. Always review the source terms yourself before redistributing images or
checkpoints. A public download link is not automatically permission to redistribute.

## Commands

List datasets:

```powershell
python training\download_datasets.py --list
```

Download and prepare one dataset:

```powershell
python training\download_datasets.py plantdoc
python training\prepare_dataset.py plantdoc
```

For a quick pipeline check, cap the prepared images and training batches:

```powershell
python training\prepare_dataset.py plantdoc --max-per-class 30
python training\train_crop_model.py plantdoc --crop PlantDocSmoke --epochs 1 --max-batches 2
```

Do not use `--register` for an experiment. For a production candidate, prepare the complete
dataset, train without `--max-batches`, inspect the test accuracy, macro F1, and confusion
matrix in the generated `.metrics.json`, and only then use `--register`.

## Adding another crop

1. Confirm the source, labels, license/terms, and whether field conditions are represented.
2. Add an entry to `training/datasets.json` with canonical labels such as
   `Bean___healthy` or `Cassava___mosaic_disease`.
3. Download, validate, deduplicate, and group burst/sequence neighbors with the supplied scripts.
4. Keep a held-out test split and inspect per-class failures, not only overall accuracy.
5. Test non-leaf images and unfamiliar crops; the leaf gate is not a substitute for
   out-of-distribution evaluation.
6. Register only a model that meets the accuracy and safety target for its intended users.

## Important limitation

The OpenCLIP leaf gate is a semantic safety filter, not a botanical guarantee. A clear leaf
should pass and unrelated objects should be rejected, but edge cases such as leaf-shaped art,
distant vegetation, fruit-only photos, or severely blurred leaves can still be wrong. The UI
therefore asks for a close, well-lit photograph of a living leaf.
