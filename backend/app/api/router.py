"""Composable root and v1 routers.

Feature modules can be attached to ``api_v1_router`` without changing the
application factory or the health endpoint prefix.
"""

from fastapi import APIRouter

from app.api.v1 import feature_router, health, me

api_router = APIRouter()
api_v1_router = APIRouter(prefix="/api/v1")

api_router.include_router(health.router)
api_v1_router.include_router(me.router)
api_v1_router.include_router(feature_router.router)
api_router.include_router(api_v1_router)

__all__ = ["api_router", "api_v1_router"]
