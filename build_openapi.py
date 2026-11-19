"""
Generate OpenAPI schema from FastAPI app.

NOTE - Flask -> FastAPI migration notes:
- Flask used Flasgger
- FastAPI auto-generates OpenAPI schema from route definitions and Pydantic models

Usage:
    python build_openapi.py

Outputs:
    - openapi/openapi.json
    - openapi/swagger.yaml
"""

import json

import yaml

from manifestservice.main import app


def generate_openapi():
    """
    Generate and save OpenAPI schema from FastAPI app.
    """
    openapi_schema = app.openapi()

    with open("openapi/openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("Generated openapi/openapi.json")

    with open("openapi/swagger.yaml", "w") as f:
        yaml.dump(openapi_schema, f, default_flow_style=False, sort_keys=False)
    print("Generated openapi/swagger.yaml")


if __name__ == "__main__":
    generate_openapi()
