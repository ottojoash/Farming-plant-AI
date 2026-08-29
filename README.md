# Plant AI - Smart Plant Disease Detection

> Competition development is tracked on the `agent` branch. See the
> [pre-hackathon baseline and disclosure](docs/competition/PRE_HACKATHON_BASELINE.md),
> the [problem and success measures](docs/competition/PROBLEM_AND_METRICS.md),
> the [versioned evaluation harness](evaluation/README.md), and the
> [Improvement Changelog](docs/competition/IMPROVEMENT_CHANGELOG.md).

Plant AI is a Flask application that screens plant-leaf photos for signs of disease. It combines:

1. An OpenCLIP leaf gate that rejects unrelated photos before classification.
2. A local ResNet34 classifier trained on 38 healthy and diseased leaf classes from 14 crops.
3. Optional crop-specific models trained with the included dataset pipeline.
4. An optional LangChain and OpenAI vision fallback for low-confidence images or plants outside the local dataset.
5. A typed LangGraph workflow that routes rejection, local inference, optional AI assistance, and safe failures.

The fallback is an AI-assisted assessment, not additional training of the ResNet model. New classes require a labelled dataset, evaluation, and model retraining before they become supported local predictions.

## Features

- Local inference using the included PyTorch checkpoint
- Leaf-only validation that rejects cars, buildings, people, and other unrelated images
- Explicit original, bean, and field-model selection, plus optional experimental comparison
- Dataset download, preparation, evaluation, and crop-model registration tools
- Confidence score and configurable acceptance threshold
- Optional multimodal LangChain fallback with validated structured output
- Typed LangGraph orchestration with conditional branches, bounded AI retries, and sanitized traces
- Context-aware intake that pauses weak results to request only missing crop and symptom details
- JPEG, PNG, and WebP validation with a 5 MB upload limit
- Clear separation between local-model and AI-assisted results
- Health-check endpoint at `/health`
- Mobile-friendly upload and result pages
- Automated route, upload, and class-mapping tests
- Shared user/admin authentication with hashed passwords and CSRF-protected forms
- Anonymous two-scan trial and configurable free monthly scan allowance
- Premium unlimited scanning with metadata-only plant history used as bounded, account-owned agent memory
- Role-based user and administrator dashboards
- Administrator-managed pricing, limits, users, plans, and upgrade approvals

## Supported local classes

The original model contains 38 classes across Apple, Blueberry, Cherry, Corn, Grape, Orange,
Peach, Bell Pepper, Potato, Raspberry, Soybean, Squash, Strawberry, and Tomato. The registered
bean specialist adds healthy common bean, anthracnose, and bean rust. The PlantDoc field model
adds a second opinion for 27 field-image classes.

See [the complete class list](Src/README.md).

## Responsible use

Plant AI provides preliminary screening, not a confirmed diagnosis. Similar symptoms can result from pathogens, pests, nutrient problems, water stress, chemical injury, or physical damage. Some conditions require a plant diagnostic laboratory for confirmation.

Do not apply pesticides based only on an image prediction. Confirm the problem, follow locally registered product labels, and seek advice from a local agricultural extension officer when appropriate.

Reference guidance:

- [University of Minnesota Extension: diagnostic photo guidance](https://extension.umn.edu/crop-production/digital-crop-doc)
- [UC Integrated Pest Management: understanding pesticides](https://ipm.ucanr.edu/home-and-landscape/understanding-pesticides/)

## Requirements

- Python 3.11 or 3.12 is recommended
- Approximately 1 GB of free space for PyTorch and application dependencies
- An OpenAI Platform API key only if the optional AI fallback is enabled

## Installation

From the repository root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Flask\requirements.txt
```

For NVIDIA GPU training, install the CUDA build after the base dependencies:

```powershell
python -m pip install --upgrade --force-reinstall -r Flask\requirements-cuda.txt
python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

If Python 3.11 is unavailable, use another supported Python installation and adjust the first command.

## Configuration

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

For local-only classification, no API key is required. To enable the fallback, set this value in `.env`:

```dotenv
OPENAI_API_KEY=your-key-here
```

Other useful settings:

```dotenv
OPENAI_VISION_MODEL=gpt-5.6-sol
OPENAI_REASONING_EFFORT=low
LOCAL_CONFIDENCE_THRESHOLD=0.75
LEAF_VALIDATION_THRESHOLD=0.60
LEAF_VALIDATOR_MODEL=ViT-B-32-quickgelu
LEAF_VALIDATOR_WEIGHTS=openai
FLASK_SECRET_KEY=replace-with-a-long-random-value
FLASK_DEBUG=false
```

Never commit `.env` or an API key. If a key has previously been committed, revoke it and remove it from published Git history.

### Database and accounts

Plant AI supports MariaDB/MySQL through SQLAlchemy. Configure the application in `.env`:

```dotenv
DATABASE_URL=mariadb+mariadbconnector://plant_app:url_encoded_password@127.0.0.1:3306/plant
ALLOW_DATABASE_FALLBACK=false
ADMIN_NAME=Plant AI Administrator
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=use-a-unique-long-password
```

Create the database and a dedicated application account as a database administrator:

```sql
CREATE DATABASE IF NOT EXISTS plant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'plant_app'@'localhost' IDENTIFIED BY 'replace-with-a-long-database-password';
GRANT ALL PRIVILEGES ON plant.* TO 'plant_app'@'localhost';
FLUSH PRIVILEGES;
```

On the first successful connection, Plant AI creates its tables, default prices and limits, and
the initial administrator from the `ADMIN_*` environment variables. Remove `ADMIN_PASSWORD`
from `.env` after confirming the account exists. Avoid using the database root account in the
application.

For local development only, a SQLite fallback can be enabled:

```dotenv
DATABASE_FALLBACK_URL=sqlite:///plant_ai.db
ALLOW_DATABASE_FALLBACK=true
```

The `/health` response reports `mysql`, `sqlite`, or `sqlite_fallback` so deployment mistakes are
visible.

## Accounts, plans, and scan rules

- Visitors can complete two successful plant scans before being prompted to register.
- Free accounts receive five scans per calendar month by default. Free results are not retained.
- Monthly and Yearly accounts receive unlimited scans and a metadata-only plant history. Uploaded
  images are never stored by this application.
- Each new paid-plan history record includes a detail page with the crop, condition, confidence,
  model evidence, saved guidance, observations, possible causes, recommended actions, warnings,
  source, and timestamp. Older records remain available with their original basic metadata.
- Administrators use the same login page and are redirected to the role-protected admin dashboard.
- The default premium price is $20 monthly or $240 yearly. Administrators can change both prices,
  the anonymous trial allowance, and the free monthly allowance.
- Monthly and Yearly checkout uses Flutterwave Standard when `FLW_PUBLIC_KEY` and `FLW_SECRET_KEY`
  are configured. Plant AI verifies the transaction reference, status, amount, currency, and customer
  before activating access.

### Flutterwave subscriptions

Add Flutterwave test keys before testing payments, then replace them with live keys only for a public
HTTPS deployment:

```dotenv
FLW_PUBLIC_KEY=FLWPUBK_TEST-...
FLW_SECRET_KEY=FLWSECK_TEST-...
FLW_SECRET_HASH=choose-the-same-secret-in-the-Flutterwave-dashboard
FLW_CURRENCY=USD
APP_BASE_URL=https://your-public-plant-ai-domain.example
```

Configure the Flutterwave webhook URL as:

```text
https://your-public-plant-ai-domain.example/webhooks/flutterwave
```

The webhook verifies its HMAC-SHA256 signature and re-verifies the transaction with Flutterwave.
Callbacks and repeated webhooks are handled idempotently. Never place Flutterwave secret keys in
source control or expose them to browser code.

### Role-aware dashboard navigation

Signed-in accounts use a responsive sidebar with short, consistent destinations:

- Free users: Overview, Scan Plant, Plan & Usage, and Account Settings.
- Premium users: all free destinations plus Scan History.
- Administrators: Overview, Scan Plant, Users, Upgrade Requests, Plans & Limits, Scan Records,
  System Status, and Account Settings.

Each destination has its own protected route. The current page is marked visually and with
`aria-current="page"`; the sidebar becomes a keyboard-accessible menu on smaller screens.

## Run the application

Development:

```powershell
Set-Location Flask
python app.py
```

Open the address printed by Flask (normally <http://127.0.0.1:5000>, or the
`FLASK_PORT` configured in `.env`).

Production-style local server:

```powershell
Set-Location Flask
waitress-serve --host=127.0.0.1 --port=5000 app:app
```

## Run tests

```powershell
python -m pytest Flask\tests -q
```

## How hybrid diagnosis works

```text
Uploaded image
      |
      v
Validate/decode image and enter typed agent state
      |
      v
Intake node -> OpenCLIP leaf gate -- not a leaf --> reject with upload guidance
      |
      v
Vision node runs original and all registered crop models
      |
      v
Crop-aware local selection
      |
      +-- confidence >= threshold --> known-class guidance
      |
      +-- confidence < threshold
              |
              +-- API configured --> structured AI node (maximum two attempts)
              |                              |
              |                              +-- failure --> cautious local fallback
              |
              +-- no API ----------> uncertain local result and warning

Any required-tool failure routes to a safe escalation result rather than a diagnosis.
```

The vision fallback uses structured fields for plant name, likely condition, visible observations, possible causes, next steps, and uncertainty. It is instructed not to provide pesticide products or dosages.

## Multi-crop datasets and training

The reproducible pipeline in `training/` currently catalogues beans, cassava, rice/paddy,
and PlantDoc field images. Dataset files are deliberately ignored by Git because they are
large and may have separate terms. Read [DATASETS.md](DATASETS.md) before downloading or
publishing a trained model.

Typical workflow:

```powershell
# Download and prepare a freely downloadable dataset
python training\download_datasets.py beans_tanzania
python training\prepare_dataset.py beans_tanzania

# Train, evaluate on the held-out test split, then register it in the app
python training\train_crop_model.py beans_tanzania --crop Beans --epochs 12 --register
```

The app discovers registered checkpoints from `Models/registry.json` and exposes them in the
model selector. The original 14-crop model is the safe default; choosing Beans or PlantDoc Field
runs only that checkpoint. An experimental option compares all models and shows every result, but
explicit selection is recommended because zero-shot crop routing is not reliable for every field
photo. A model is registered only after a full run; smoke-test checkpoints are never registered.

## Training and evaluation guidance

The original training notebook is in [Src/Plant Disease Identification.ipynb](Src/Plant%20Disease%20Identification.ipynb). Before adding a new plant or disease to the local model:

1. Collect licensed, labelled images representing field conditions.
2. Create separate training, validation, and test splits without near-duplicate leakage.
3. Update the final model layer and class registry.
4. Retrain and measure per-class precision, recall, F1 score, and confusion matrices.
5. Test unrelated images and define a calibrated rejection threshold.
6. Version the dataset, checkpoint, preprocessing, and evaluation report together.

## Project layout

```text
Flask/
  app.py              Flask routes, validation, and hybrid routing
  ai_diagnosis.py     LangChain multimodal fallback
  model.py            ResNet34 loading and inference
  utils.py            Known-class educational guidance
  templates/          Web pages
  static/              Styles and images
  tests/               Automated tests
Models/                Local ResNet34 checkpoint
training/              Dataset catalogue, preparation, training, and evaluation
Src/                   Training notebook and class documentation
TestImages/            Small manual test set
```

## Security note

An API key was previously present in repository history. Removing the current source file does not invalidate that credential or erase older commits. The owner must revoke the key in the OpenAI Platform and rewrite published history if this repository has been shared.

## License

Licensed under the [MIT License](LICENSE).
