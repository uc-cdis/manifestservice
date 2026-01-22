# manifestservice/config.py
"""
Pydantic Settings configuration for Manifest Service.

Configuration is loaded from a JSON file (config.json or
path specified in MANIFEST_SERVICE_CONFIG_PATH).

NOTE - This replaces the Flask app.config dict for FastAPI migration.
"""

import json
import os
from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


TRUSTED_CONFIG_PATH_PREFIXES = [os.getcwd(), "/var/gen3"]


def validate_config_path(config_path: str) -> None:
    """
    Validate that the config file path is within trusted directories.

    Args:
        config_path: Path to the configuration file to validate.

    Raises:
        ValueError
    """
    for trusted_path in TRUSTED_CONFIG_PATH_PREFIXES:
        if (
            os.path.commonpath((os.path.realpath(config_path), trusted_path))
            == trusted_path
        ):
            return
    raise ValueError(f"Illegal config file path provided as {config_path}")


class Settings(BaseSettings):
    """
    Application settings loaded from config.json.

    Settings:
    - manifest_bucket_name (REQUIRED): S3 bucket for storing manifests
    - hostname (REQUIRED): The hostname of the Gen3 deployment
    - prefix: Optional folder prefix in S3 bucket
    - oidc_issuer: Derived from hostname (https://{hostname}/user)
    - user_api: URL to Fence service, can be overridden via FENCE_URL env var
    - force_issuer: Use USER_API URL for JWT key fetching (default: True)
    """

    manifest_bucket_name: str
    hostname: str
    prefix: Optional[str] = None
    oidc_issuer: str = ""
    user_api: str = "http://fence-service/"
    force_issuer: bool = True

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def load_config_file(cls, values: dict) -> dict:
        """
        Load configuration from JSON file.

        OIDC issuer is derived from hostname.
        Optionally overrides user_api from FENCE_URL environment variable.
        """
        config_path = os.environ.get("MANIFEST_SERVICE_CONFIG_PATH", "config.json")
        validate_config_path(config_path)

        try:
            with open(config_path) as f:
                config_dict = json.loads(f.read())
        except Exception as e:
            raise ValueError(
                f"Unable to parse the provided config file at {config_path}"
            ) from e

        for key, value in config_dict.items():
            lower_key = key.lower()
            if lower_key not in values or values[lower_key] is None:
                values[lower_key] = value

        if fence_url := os.environ.get("FENCE_URL"):
            values["user_api"] = fence_url

        if hostname := values.get("hostname"):
            values["oidc_issuer"] = f"https://{hostname}/user"

        # Check required config variables exist and are not None
        required_config_variables = ["hostname", "manifest_bucket_name"]
        provided_keys = set(values.keys())
        missing = set(required_config_variables) - provided_keys
        missing.update(
            key
            for key in required_config_variables
            if key in provided_keys and values.get(key) is None
        )
        if missing:
            raise ValueError(
                "Not all required config variables were provided in {}. Missing: {}".format(
                    config_path,
                    str(missing),
                )
            )

        return values


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()


def clear_settings_cache() -> None:
    """
    Clear the settings cache.
    """
    get_settings.cache_clear()
