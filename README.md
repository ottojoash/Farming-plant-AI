# Plant AI - Smart Plant Disease Detection

Plant AI is a Flask application that screens plant photos for signs of disease. It combines:

1. A local ResNet34 classifier trained on 38 healthy and diseased leaf classes from 14 crops.
2. An optional LangChain and OpenAI vision fallback for low-confidence images or plants outside the local dataset.

The fallback is an AI-assisted assessment, not additional training of the ResNet model. New classes require a labelled dataset, evaluation, and model retraining before they become supported local predictions.

## Features

- Local inference using the included PyTorch checkpoint
- Confidence score and configurable acceptance threshold
- Optional multimodal LangChain fallback with validated structured output
- JPEG, PNG, and WebP validation with a 5 MB upload limit
- Clear separation between local-model and AI-assisted results
- Health-check endpoint at `/health`
- Mobile-friendly upload and result pages
- Automated route, upload, and class-mapping tests

## Supported local classes

The local model contains 38 classes across Apple, Blueberry, Cherry, Corn, Grape, Orange, Peach, Bell Pepper, Potato, Raspberry, Soybean, Squash, Strawberry, and Tomato.

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
FLASK_SECRET_KEY=replace-with-a-long-random-value
FLASK_DEBUG=false
```

Never commit `.env` or an API key. If a key has previously been committed, revoke it and remove it from published Git history.

## Run the application

Development:

```powershell
Set-Location Flask
python app.py
```

Open <http://127.0.0.1:5000>.

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
Validate and decode image
      |
      v
Local ResNet34 prediction
      |
      +-- confidence >= threshold --> known-class guidance
      |
      +-- confidence < threshold
              |
              +-- API key configured --> LangChain vision assessment
              |
              +-- no API key ---------> uncertain local result and warning
```

The vision fallback uses structured fields for plant name, likely condition, visible observations, possible causes, next steps, and uncertainty. It is instructed not to provide pesticide products or dosages.

## Training and evaluation

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
Src/                   Training notebook and class documentation
TestImages/            Small manual test set
```

## Security note

An API key was previously present in repository history. Removing the current source file does not invalidate that credential or erase older commits. The owner must revoke the key in the OpenAI Platform and rewrite published history if this repository has been shared.

## License

Licensed under the [MIT License](LICENSE).
