"""
FastAPI dependencies for auth and config injection.

NOTE - Flask -> FastAPI migration notes:
- Use FastAPI Depends() Instead of _authenticate_user()
- Use authutils.token.fastapi.access_token() instead of authutils.token.validate (flask)
- User folder name function put here for now

Flask way:
    @blueprint.route("/")
    def get_manifests():
        err, code = _authenticate_user()
        if err is not None:
            return err, code
        folder = _get_folder_name_from_token(current_token)  # Global proxy
        ...

FastAPI way:
    @router.get("/")
    def get_manifests(
        claims: CurrentUserClaims,
        settings: SettingsDep,
    ):
        folder = get_user_folder_name(claims, settings)
        ...
"""

from typing import Annotated

from authutils.token.fastapi import access_token
from fastapi import Depends

from .config import Settings, get_settings


_settings = get_settings()
_validate_and_get_claims = access_token(
    "user",
    "openid",
    issuer=_settings.oidc_issuer,
    purpose="access",
    force_issuer=_settings.user_api if _settings.force_issuer else None,
)

# Annotated types for shared dependencies
# https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies

SettingsDep = Annotated[Settings, Depends(get_settings)]

CurrentUserClaims = Annotated[dict, Depends(_validate_and_get_claims)]


def get_user_folder_name(claims: dict, settings: Settings) -> str:
    """
    Returns the name of the user's manifest folder.
    The convention we'll use here is that a user's folder name will be "user-x" where x is
    their ID (integer).

    This replaces the Flask function `_get_folder_name_from_token()`.

    Args:
        claims: JWT claims dict containing "sub" (user ID)
        settings: Application settings (for prefix)

    Returns:
        Folder path for the user's data
    """
    user_id = claims["sub"]
    base_folder = f"user-{user_id}"

    if settings.prefix:
        return f"{settings.prefix}/{base_folder}"

    return base_folder
