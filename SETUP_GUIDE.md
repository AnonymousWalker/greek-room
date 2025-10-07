# Greek Room Ephesus Setup Guide

This guide documents the setup process for running the Greek Room web API and UI (Ephesus component) based on the FastAPI framework.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Git

## Setup Steps

### 1. Virtual Environment Setup

```bash
cd ephesus
python3 -m venv .virtual
source .virtual/bin/activate
```

### 2. Fix Package Configuration

The `pyproject.toml` file needed to be updated to properly handle the package structure:

**File**: `ephesus/pyproject.toml`

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ephesus"
version = "0.1.0"
description = "Greek Room Web API and Reference Application"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "alembic==1.16.1",
    "babel==2.17.0",
    "fastapi==0.115.12",
    "jinja2==3.1.6",
    "pydantic-settings==2.9.1",
    "python-multipart==0.0.20",
    "redis==6.1.0",
    "sil-machine==1.7.0",
    "sqlalchemy==2.0.41",
    "uvicorn[standard]==0.34.2",
    "wildebeest-nlp==0.9.2",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["ephesus*"]
```

### 3. Environment Configuration

Create a local environment file:

**File**: `ephesus/.env.local`

```env
# Development Environment Configuration for Ephesus

## Ephesus environment
EPHESUS_ENV=development

## Ephesus properties
EPHESUS_PROJECTS_DIR=/home/tony-tran/dev/greek-room/ephesus/data/projects
EPHESUS_STATIC_RESULTS_DIR=/home/tony-tran/dev/greek-room/ephesus/data/analysis-requests
EPHESUS_DEFAULT_VREF_FILE=/home/tony-tran/dev/greek-room/ephesus/data/vref.txt

## Email properties
EPHESUS_EMAIL_PORT=587
EPHESUS_EMAIL_HOST=smtp.gmail.com
EPHESUS_SUPPORT_EMAIL=support@greekroom.org

## SQLite DB properties (for development)
SQLALCHEMY_DATABASE_URI=sqlite:////home/tony-tran/dev/greek-room/ephesus/data/ephesus.db

## Redis DB properties (for development - will use local Redis)
REDIS_CONNECTION_URI=redis://localhost:6379/1?decode_responses=True&protocol=3
```

Update the config to use the local environment file:

**File**: `ephesus/ephesus/config.py`

```python
model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")
```

### 4. Docker Compose Configuration

Configure the Docker services with proper development values:

**File**: `ephesus/docker-compose/postgres.env`

```env
## PostgreSQL DB Configuration

POSTGRES_DB=ephesus_db
POSTGRES_USER=ephesus_user
POSTGRES_PASSWORD=ephesus_password
```

**File**: `ephesus/docker-compose/keycloak.env`

```env
## Keycloak Configuration

# KC_LOG_LEVEL=DEBUG

KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin123

KC_DB=postgres
KC_DB_USERNAME=ephesus_user
KC_DB_PASSWORD=ephesus_password
KC_DB_URL=jdbc:postgresql://postgres:5432/ephesus_db

KC_PROXY=edge
KC_HOSTNAME_STRICT=false
KC_HTTP_RELATIVE_PATH=
KC_HOSTNAME_URL=http://localhost:8080
KC_HOSTNAME_ADMIN_URL=http://localhost:8080

KC_FEATURES=declarative-user-profile
```

**File**: `ephesus/docker-compose/ephesus.env`

```env
# Environment config

## Ephesus environment
EPHESUS_ENV=development

## Ephesus properties
EPHESUS_ROOT_DIR=/ephesus
EPHESUS_PROJECTS_DIR=/data/projects
EPHESUS_STATIC_RESULTS_DIR=/analysis-requests
EPHESUS_DEFAULT_VREF_FILE=/ephesus/data/vref.txt

## Email properties
EPHESUS_EMAIL_PORT=587
EPHESUS_EMAIL_HOST=smtp.gmail.com
EPHESUS_SUPPORT_EMAIL=support@greekroom.org

## SQLite DB properties
SQLALCHEMY_DATABASE_URI=sqlite:////data/ephesus.db

## Redis DB properties
REDIS_CONNECTION_URI=redis://redis:6379/1?decode_responses=True&protocol=3
```

**File**: `ephesus/docker-compose/oauth2proxy.env`

```env
## Oauth2proxy Configuration

OAUTH2_PROXY_PROVIDER=keycloak-oidc

OAUTH2_PROXY_CLIENT_ID=ephesus-client
OAUTH2_PROXY_CLIENT_SECRET=ephesus-secret
OAUTH2_PROXY_OIDC_ISSUER_URL=http://localhost:8080/realms/master
OAUTH2_PROXY_WHITELIST_DOMAINS=localhost
OAUTH2_PROXY_CODE_CHALLENGE_METHOD=S256
OAUTH2_PROXY_EMAIL_DOMAINS=*

OAUTH2_PROXY_SET_XAUTHREQUEST=true
OAUTH2_PROXY_PASS_ACCESS_TOKEN=true
OAUTH2_PROXY_SKIP_JWT_BEARER_TOKENS=true
OAUTH2_PROXY_VALIDATE_URL=http://localhost:8080/realms/master/protocol/openid-connect/userinfo

OAUTH2_PROXY_COOKIE_SECURE=false
OAUTH2_PROXY_COOKIE_NAME=_oauth2_proxy
OAUTH2_PROXY_COOKIE_SECRET=ephesus-cookie-secret-123

OAUTH2_PROXY_REVERSE_PROXY=true
OAUTH2_PROXY_SKIP_PROVIDER_BUTTON=true
OAUTH2_PROXY_HTTP_ADDRESS=0.0.0.0:4180
OAUTH2_PROXY_PROVIDER_CA_FILE=

OAUTH2_PROXY_UPSTREAM=http://ephesus:8000/
```

### 5. Database Setup

Update Alembic configuration to include models:

**File**: `ephesus/ephesus/database/alembic/env.py`

```python
# add your model's MetaData object here
# for 'autogenerate' support
from ephesus.database.setup import Base
from ephesus.database.models import user_projects

target_metadata = Base.metadata
```

Create necessary directories:

```bash
mkdir -p ephesus/data/projects ephesus/data/analysis-requests
mkdir -p ephesus/ephesus/database/alembic/versions
```

### 6. Install Dependencies

```bash
cd ephesus
source .virtual/bin/activate
pip install -e .
```

### 7. Database Migration

Create and run the initial migration:

```bash
# Create migration
alembic -c ephesus/database/alembic.ini revision --autogenerate -m "Initial migration"

# Fix the generated migration file to use standard SQLAlchemy DateTime instead of custom TZDateTime
# Edit the migration file and replace:
# ephesus.database.custom.TZDateTime(timezone=True) -> DateTime(timezone=True)

# Run migration
alembic -c ephesus/database/alembic.ini upgrade head
```

### 8. Start Services

Start the database and Redis services:

```bash
cd ephesus/docker-compose
docker compose up -d postgres redis
```

Start the FastAPI application:

```bash
cd ephesus
source .virtual/bin/activate
uvicorn ephesus.main:app --host 0.0.0.0 --port 8000 --reload
```

## Verification

Once everything is running, you can verify the setup:

- **Web UI**: http://localhost:8000/
- **API Documentation**: http://localhost:8000/docs
- **Available API endpoints**:
  - `/api/v1/projects` - Project management
  - `/api/v1/projects/{project_resource_id}/reference` - Reference materials
  - `/api/v1/projects/{resource_id}/wildebeest` - Wildebeest analysis
  - `/projects/{resource_id}/overview` - Project overview UI
  - `/projects/{resource_id}/wildebeest` - Wildebeest UI

## Key Changes Made

1. **Fixed package structure** in `pyproject.toml` to resolve build errors
2. **Created development environment configuration** with proper paths and settings
3. **Configured Docker services** with development-friendly credentials and settings
4. **Set up database migrations** with proper model imports and fixed custom type issues
5. **Created necessary directories** for data storage and migrations
6. **Configured OAuth2 proxy** for authentication (optional, not started by default)

## Notes

- The setup uses SQLite for development database (easier than PostgreSQL for local development)
- Redis is used for caching and session management
- Keycloak and OAuth2 proxy are configured but not started by default (can be started if authentication is needed)
- The application runs on port 8000 with auto-reload enabled for development

## Troubleshooting

- If you get import errors, make sure the virtual environment is activated
- If database migration fails, check that all environment variables are set correctly
- If Docker services fail to start, ensure Docker is running and ports 5432 and 6379 are available
- For authentication issues, refer to the Keycloak and OAuth2 proxy configurations
