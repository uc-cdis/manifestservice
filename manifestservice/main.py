"""
FastAPI app factory pattern Manifest Service.

NOTE - Flask -> FastAPI migration notes:
- Uses FastAPI instead of Flask
- Uses lifespan context manager
- Config loaded via Pydantic Settings config.py instead of flask app.config
- Health check returns JSON {"status": "Healthy"} instead of plain txt "Healthy"
- Uses uvicorn for run_for_development
- Uses /docs for Swagger UI (FastAPI default), replaces flasgger
- OpenAPI schema auto-generated from route definitions and Pydantic models
"""

import logging
from contextlib import asynccontextmanager
from importlib.metadata import version
from typing import AsyncGenerator

from cdislogging import get_logger
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import get_settings, clear_settings_cache

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
        version=version("manifestservice"),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Register routers
    # NOTE: Router registration to be added
    # from .routers import manifests
    # app.include_router(manifests.router)

    @app.get("/_status", tags=["system"])
    def health_check() -> dict:
        """
        Health check endpoint
        """
        return {"status": "Healthy"}

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
