# Reproducibility notes

- **Environment:** Python 3.13.2 on Windows 10; numpy 2.2.3, scipy 1.15.2, scikit-learn 1.6.1, pytest 9.1.1 (`requirements.txt`). Each run's `MANIFEST.json` records the Python, platform and library versions actually used.
- **Randomness:** split seed `split.seed`; inner folds use `seed + 1000 + i`; bootstrap seed `evaluation.bootstrap_seed`; synthetic generator seed `--seed`. lbfgs logistic regression is deterministic given data and settings.
- **Fitted on training data only:** encoder vocabularies, rare-level pooling, interaction cells, type-prior rates, logistic coefficients. Calibrators and error-analysis thresholds are fitted on the validation (unseen-publisher) partition. Nothing is fitted on test.
- **Frozen before labels (real runs):** feature schema, label schema, type map, topic taxonomy, topic–remit map, role-rule table. Their hashes belong in the data manifest; `bundle.json` stores the feature- and label-schema SHA-256 and refuses to load if the feature schema has changed.
- **Serialisation:** models, encoders and calibrators are stored as plain JSON (`model/bundle.json`, no pickle) with `bundle.sha256`; loading verifies the checksum. `MANIFEST.json` lists SHA-256 for every output file.
- **Test opening:** a real run with `--open-test` writes `TEST_OPENED.lock`; a second opening is refused. The smoke command deletes its own lock because synthetic runs may be repeated.
- **Data provenance:** a real run requires a data manifest (template: `docs/DATA_MANIFEST.template.json`) declaring authorisation, provenance, usage rights, human label source and guideline version. The data file's SHA-256 is recorded in the report and bundle.
- **Reproducing the smoke run:** `PYTHONPATH=src python -m fha.cli smoke --seed 0` regenerates `outputs/synthetic_smoke/` (timestamps differ; numbers should match on the same library versions).
