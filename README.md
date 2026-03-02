# Manifest Service

## Overview

This service handles reading from and writing to a user's S3 folder containing their manifests, cohorts, and metadata export files. A manifest is a JSON file that lists records a researcher may be interested in analyzing. This service stores files to a user folder in an S3 bucket and delivers them for later use, such as when the researcher wants to mount the manifest in their workspace. If the `prefix` config variable is set, user folders will be stored in a directory of that name within the S3 bucket.

### Manifest Format

Manifest files should contain JSON of the form:

```json
[
  {
    "object_id": "757508f5-2697-4700-a69f-89d173a4c514",
    "subject_id": "da6a14a0-6498-4941-a1b2-bbe45a2ccac2"
  },
  {
    "object_id": "835db5c6-5cc8-4d70-a3b2-9a18ad4912cd",
    "subject_id": "da6a14a0-6498-4941-a1b2-bbe45a2ccac2"
  }
]
```

Each record must contain at least an `object_id` key. Additional keys are preserved.

## Endpoints

For all endpoints (except `/_status`), the request must contain an `Authorization` header with a valid access token. The user needs read access and read-storage access on at least one project in order to use this service.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/_status` | Health check (no auth required) |
| GET | `/` | List user's manifests |
| POST/PUT | `/` | Create a manifest file |
| GET | `/file/{filename}` | Read manifest file contents |
| GET | `/cohorts` | List user's cohorts |
| POST/PUT | `/cohorts` | Add a PFB GUID as a cohort |
| GET | `/metadata` | List user's metadata exports |
| POST/PUT | `/metadata` | Create a metadata export file |
| GET | `/metadata/{filename}` | Read metadata file contents |

On failure, endpoints return JSON in the form:

```json
{ "detail": "error message" }
```

## API Documentation

The [OpenAPI](https://github.com/OAI/OpenAPI-Specification)/[Swagger](https://swagger.io/) specification is stored in the `openapi/` directory and can be visualized [here](http://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/manifestservice/master/openapi/swagger.yaml).

To regenerate the static OpenAPI files:

```bash
python build_openapi.py
```

FastAPI also serves interactive docs at `/docs` (Swagger UI), `/redoc`, and `/openapi.json` when running locally.

## Running the Service Locally

1. Fill out `config.json` with the correct values (see [Configuration](#configuration))
2. Install dependencies and run:

```bash
poetry install
python run.py
```

The service starts at `http://localhost:8000/`.

You'll need AWS credentials in your environment to run this locally.

## Configuration

The service loads configuration from `config.json` (or the path in `MANIFEST_SERVICE_CONFIG_PATH` env var). Required fields:

| Key | Required | Description |
|-----|----------|-------------|
| `MANIFEST_BUCKET_NAME` | Yes | S3 bucket for storing user data |
| `hostname` | Yes | Hostname of the Gen3 deployment |
| `prefix` | No | Optional folder prefix in S3 bucket |

Environment variable overrides:
- `MANIFEST_SERVICE_CONFIG_PATH` — Path to config file (default: `config.json`)
- `FENCE_URL` — Override the Fence service URL (default: `http://fence-service/`)

## Development

### Install Dependencies

```bash
poetry install
```

### Run Tests

```bash
poetry run pytest tests/ -v
```

## Quickstart with Helm

You can deploy individual services via Helm.
Please refer to the [Helm quickstart guide](https://github.com/uc-cdis/manifestservice/blob/master/docs/quickstart_helm.md).
