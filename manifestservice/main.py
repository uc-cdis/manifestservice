"""
FastAPI app for Manifest Service.

NOTE - Flask -> FastAPI migration notes:
- Uses FastAPI instead of Flask
- Uses lifespan context manager
- Config loaded via Pydantic Settings config.py instead of flask app.config
- Health check returns JSON {"status": "Healthy"} instead of plain txt "Healthy"
- Uses uvicorn for run_for_development
- Uses /docs for Swagger UI (FastAPI default), replaces flasgger
- OpenAPI schema auto-generated from route definitions and Pydantic models
- Exception handlers registered for S3 errors and generic exceptions
"""

import logging
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import AsyncGenerator

from cdislogging import get_logger
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings, clear_settings_cache
from .errors import register_error_handlers
from .routers import manifests_router
from .schemas import HealthCheckResponse

logger = get_logger("manifestservice_logger", log_level="info")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Parse the configuration, setup and instantiate necessary classes.
    """
    # load settings
    settings = get_settings()
    logger.info(
        f"Starting Manifest Service with bucket: {settings.manifest_bucket_name}"
    )
    logger.info(f"OIDC Issuer configured as: {settings.oidc_issuer}")

    yield

    # cleanup
    clear_settings_cache()
    logger.info("Shutting down Manifest Service")


def create_app() -> FastAPI:
    """
    Application factory for Manifest Service.

    Returns:
        FastAPI: Configured FastAPI app instance
    """
    app = FastAPI(
        title="Manifest Service",
        description=(
            "A microservice that facilitates manifest creation and retrieval.\n\n"
            "Code is available on [GitHub](https://github.com/uc-cdis/manifestservice)."
        ),
        version=version("manifestservice"),
        contact={
            "name": "CTDS UChicago",
            "email": "cdis@uchicago.edu",
        },
        license_info={
            "name": "Apache 2.0",
            "url": "http://www.apache.org/licenses/LICENSE-2.0.html",
        },
        openapi_tags=[
            {
                "name": "manifests",
                "description": "Operations for managing user manifest files (lists of object IDs).",
            },
            {
                "name": "cohorts",
                "description": "Operations for managing cohort exports (PFB GUIDs).",
            },
            {
                "name": "metadata",
                "description": "Operations for managing exported metadata files.",
            },
            {
                "name": "system",
                "description": "System health and status endpoints.",
            },
        ],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    app.include_router(manifests_router)

    @app.get("/_status", tags=["system"], summary="Health check")
    def health_check() -> HealthCheckResponse:
        """
        Health check endpoint
        """
        return HealthCheckResponse(status="Healthy")

    return app


app = create_app()


def run_for_development(**kwargs) -> None:
    """
    Run the app for local development.
    """
    import uvicorn

    uvicorn.run(
        "manifestservice.main:app",
        host=kwargs.get("host", "127.0.0.1"),
        port=kwargs.get("port", 8000),
        reload=kwargs.get("reload", True),
        log_level=kwargs.get("log_level", "info"),
    )
