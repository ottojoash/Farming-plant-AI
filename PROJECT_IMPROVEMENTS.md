# Plant AI — Project Improvement Roadmap

## Project title

**Plant AI — Smart Plant Disease Detection**

Plant AI uses a ResNet34 image-classification model to identify 38 healthy and diseased leaf classes across 14 plant types. The following improvements are recommended before the application is deployed or used for real farming decisions.

## Priority 1: Security and critical bugs

- [ ] Revoke the OpenAI API key exposed in the source code and Git history.
- [ ] Remove all hard-coded credentials from the repository.
- [ ] Read `OPENAI_API_KEY` from an environment variable and provide a safe `.env.example` file.
- [ ] Correct the `Tomato___Target_Spo` key in `Flask/utils.py` to `Tomato___Target_Spot`.
- [ ] Fix the prediction fallback in `Flask/app.py`, which currently uses `res` before it has been assigned.
- [ ] Disable Flask debug mode in production.
- [ ] Avoid marking generated or external text as trusted HTML unless it has been sanitized.

## Priority 2: Safer and more useful predictions

- [ ] Return the model's confidence score with every prediction.
- [ ] Add a tested confidence threshold and return “Unable to identify safely” for uncertain images.
- [ ] Detect and reject images that do not contain a suitable plant leaf.
- [ ] Convert uploaded images to RGB before inference so grayscale and transparent images work correctly.
- [ ] Run predictions inside `torch.inference_mode()`.
- [ ] Handle corrupted and unsupported images with a clear user-facing error.
- [ ] Explain that a prediction is an AI estimate and not a guaranteed diagnosis.

## Priority 3: Upload and application security

- [ ] Accept only supported formats such as JPEG, PNG, and WebP.
- [ ] Verify actual image content instead of trusting the file extension.
- [ ] Configure a maximum upload size.
- [ ] Return proper HTTP status codes for invalid requests and server errors.
- [ ] Replace development `print` statements with structured application logging.
- [ ] Add secure production configuration through environment variables.

## Priority 4: Model quality

- [ ] Evaluate the model on real field photographs, not only clean dataset images.
- [ ] Publish per-class precision, recall, F1 score, and a confusion matrix.
- [ ] Test blurred images, shadows, cluttered backgrounds, multiple leaves, and unrelated images.
- [ ] Calibrate confidence scores before selecting a rejection threshold.
- [ ] Add regional crop and disease images from the application's intended users.
- [ ] Record the model version, dataset version, preprocessing, random seed, and training configuration.
- [ ] Add a way for users to report an incorrect result for future model improvement.

## Priority 5: User experience

- [ ] Add simple instructions for taking a useful leaf photograph.
- [ ] Show the uploaded image alongside the result.
- [ ] Present crop, disease, confidence, symptoms, causes, and suggested actions in separate sections.
- [ ] Add a “Try another image” button.
- [ ] Display a loading state while inference is running.
- [ ] Improve keyboard navigation, labels, focus states, color contrast, and alternative text.
- [ ] Refresh the visual design and ensure it works well on mobile devices.
- [ ] Correct spelling, grammar, and text-encoding problems throughout the interface and README.
- [ ] Support local languages relevant to the application's users.

## Priority 6: Agricultural guidance

- [ ] Review disease descriptions and treatment guidance with an agricultural specialist.
- [ ] Cite reliable sources for disease information.
- [ ] Separate general prevention advice from chemical treatment recommendations.
- [ ] Avoid recommending pesticides without considering crop, location, regulations, dosage, and safety requirements.
- [ ] Encourage users to consult a local agricultural extension officer when a diagnosis is uncertain or severe.

## Priority 7: Project structure and deployment

- [ ] Make the model path relative to the application file instead of the current working directory.
- [ ] Keep only one copy of the model weights.
- [ ] Store large model files using Git LFS or release/object storage.
- [ ] Remove notebook checkpoints and generated Chroma database files from Git.
- [ ] Remove unused or unfinished integration files, or complete and test their integration.
- [ ] Replace the environment dump in `Flask/requirements.txt` with a minimal set of direct dependencies.
- [ ] Pin and document a supported Python version.
- [ ] Add production server and deployment instructions.
- [ ] Add a health-check endpoint for deployment monitoring.

## Priority 8: Testing and documentation

- [ ] Add unit tests for all 38 model-class-to-description mappings.
- [ ] Add tests for valid, invalid, empty, oversized, grayscale, and transparent image uploads.
- [ ] Add Flask route and HTTP status tests.
- [ ] Add a small model smoke test using known sample images.
- [ ] Add formatting, linting, security scanning, and tests to continuous integration.
- [ ] Expand the README with installation, configuration, startup, testing, and deployment instructions.
- [ ] Document known limitations and the source and license of the dataset and model weights.

## Suggested implementation phases

### Phase 1 — Make the current application safe and stable

1. Rotate and remove the exposed API key.
2. Fix the Target Spot mapping and broken fallback.
3. Validate uploads and configure a file-size limit.
4. Add RGB conversion, inference mode, confidence reporting, and uncertain-result handling.
5. Correct HTTP responses and production configuration.

### Phase 2 — Make the project reproducible

1. Clean the dependency file and document the supported Python version.
2. Consolidate model files and remove generated artifacts.
3. Add automated tests and continuous integration.
4. Improve installation and deployment documentation.

### Phase 3 — Improve product quality

1. Redesign the upload and result experience.
2. Validate the model on real field images.
3. Review agricultural advice and add reliable citations.
4. Add feedback collection and regional or multilingual support.

## Definition of a deployment-ready first release

The first release should not be considered deployment-ready until:

- No credentials are stored in the repository or its published history.
- All 38 prediction classes map to valid result information.
- Invalid and uncertain images are rejected safely.
- Upload size and file types are validated.
- The application runs without debug mode.
- Installation and startup work from a clean environment.
- Critical prediction and upload paths have automated tests.
- Users see confidence, limitations, and an appropriate agricultural disclaimer.
