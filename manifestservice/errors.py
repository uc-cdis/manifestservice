"""
Custom exception handlers for Manifest Service.

NOTE - Flask -> FastAPI migration notes:
- Previous flask errors.py was just a re-export module
- Added generic exception handler to return 500 with safe message
- TODO - we could consider refactoring a custom handler for s3 errors
"""

from cdislogging import get_logger
from cdiserrors import *
from fastapi import Request
from fastapi.responses import JSONResponse

logger = get_logger("manifestservice", log_level="info")


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler for unexpected exceptions.
    """
    logger.exception(f"Unexpected error processing request: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred."},
    )


def register_error_handlers(app) -> None:
    """
    Register custom exception handlers with FastAPI app.
    """
    app.add_exception_handler(Exception, generic_exception_handler)
