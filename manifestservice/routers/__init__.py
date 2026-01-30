"""
FastAPI routers for Manifest Service.
"""

from .manifests import router as manifests_router

__all__ = ["manifests_router"]
