"""
Development server for Manifest Service.

Starts the FastAPI application with uvicorn.
Production will use gunicorn with uvicorn workers.
"""

from manifestservice.main import run_for_development


if __name__ == "__main__":
    run_for_development(reload=True)
