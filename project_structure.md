### Greek Room repository structure and component purposes
 
#### High-level
- **Purpose**: A suite of tools and services for Biblical NLP, combining a FastAPI web API/reference app, Python libraries/CLIs for text checks and utilities, a legacy Flask web app, and a static documentation site.
 
#### Top-level components
- **`ephesus/` — Web API and reference app (FastAPI)**
  - **Purpose**: Primary web service exposing Greek Room capabilities and a reference UI.
  - **Key parts**:
    - `ephesus/main.py`: FastAPI entry point.
    - `ephesus/auth/`: Auth routes.
    - `ephesus/home/`, `ephesus/wildebeest/`: Feature routes and templates; integrates `wildebeest-nlp` per `pyproject.toml`.
    - `ephesus/database/`: SQLAlchemy models (`models/`), CRUD, schemas, migrations via Alembic (`alembic/`, `alembic.ini`).
    - `ephesus/common/`, `ephesus/dependencies.py`, `ephesus/exceptions.py`: Shared utilities, DI, error handling.
  - **Infra/dev**:
    - `docker-compose/`: Multi-service stack (Postgres, Redis, Keycloak, OAuth2 proxy, volume backups) with env files.
    - `cron/`: DB backup scripts and crontab; restore guidance in `README.md`.
    - `Dockerfile`, `pyproject.toml` (FastAPI, SQLAlchemy, Alembic, Redis, Wildebeest, Uvicorn).
  - **What it enables**: A containerized, authenticated API with persistence and backup/restore flows, serving templates for reference usage.
 
- **`greekroom/` — Python package (library + CLIs)**
  - **Purpose**: Reusable NLP utilities and text checks, installable as a package.
  - **Subpackages**:
    - `gr_utilities/`: General utilities; notable CLI:
      - `wb_file_props.py`: Analyzes script direction and quotation punctuation; outputs JSON/HTML. Exposed as `gr-wb-file-props` (and a test runner script).
    - `owl/`: Battery of smaller translation checks; notable CLI:
      - `repeated_words.py`: Detects repeated words (e.g., “the the”), configurable by data in `owl/data/legitimate_duplicates.jsonl`. Exposed as `gr-repeated-words`.
  - **Packaging**:
    - `pyproject.toml`: Defines scripts, dependencies (regex, unicodeblock, uroman), Python 3.11+, and metadata.
  - **What it enables**: Standalone command-line tools and importable APIs for analysis and checks used by services or pipelines.
 
- **`web/` — Legacy/alternate web app (Flask)**
  - **Purpose**: A separate Flask-based application with blueprints for auth, home, example features, alignment visualization, Voithos, and Wildebeest.
  - **Key parts**:
    - `ephesus/app.py`, `wsgi.py`, `blueprints/*`, `model/*`, `common/`, `extensions.py`.
    - `requirements.txt` pins Flask app deps.
  - **What it enables**: An older or parallel web UI/API surface distinct from the FastAPI-based `ephesus`.
 
- **`site/` — Static documentation site (Hugo)**
  - **Purpose**: Public-facing documentation/content.
  - **Key parts**:
    - `content/en/*.md`: Docs pages (e.g., `wildebeest.md`, `align.md`, `spell.md`).
    - `themes/zen/`: Theme assets and layout.
    - `hugo.yaml`: Site config.
  - **What it enables**: Buildable static site for docs and marketing.
 
- **Data, scripts, and samples**
  - `html/`: Sample bilingual HTML files (e.g., `eng-hin/MAT-001.html`) for testing/demos.
  - `smart_edit_distance/`: Algorithm and data files for smart string distance scoring; core in `src/smart_edit_distance.py`.
  - `utilities/`: Standalone scripts for parallel corpora prep, formatting, and alignment visualization (e.g., `parallel-corpus-prep.py`, `ualign.py`).
  - `web/data/`: Defaults and example uploads for demos (`voithos_uploads`).
  - `instance/config.cfg`: Runtime configuration for the Flask app.
 
- **Dev/ops and misc**
  - `ephesus/docker-compose/*.env`, `redis-users.acl`: Service configs and access control for the compose stack.
  - `LICENSE`, top-level `README.md`: Project overview and CLI usage examples.
 
#### How the pieces fit
- The installable `greekroom` package provides the core NLP utilities and CLIs.
- `ephesus` wraps capabilities into a FastAPI service with DB/auth, deployable via Docker Compose with backups.
- `web` offers a Flask-based alternative/legacy app with similar domains (auth, alignment, Wildebeest).
- `site` documents features and usage.
- Additional scripts and data support preprocessing, alignment, and evaluation workflows.
 