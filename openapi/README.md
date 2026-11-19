# OpenAPI Specification

The [OpenAPI 3.1](https://github.com/OAI/OpenAPI-Specification) specification for this service is stored in two formats:
- `openapi.json`
- `swagger.yaml` - (backward compatibility)

## Viewing the Documentation

### Local Development
When running the service locally, interactive documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Raw OpenAPI JSON**: http://localhost:8000/openapi.json

### Online Viewer
The documentation can be visualized using the Swagger UI at:
`https://petstore.swagger.io/?url=<swagger.yaml raw URL>`

For example: [View current documentation](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/manifestservice/master/openapi/swagger.yaml)

## Generating/Updating the Documentation

FastAPI auto-generates the OpenAPI schema from route definitions, so documentation updates happen automatically when you:
1. Update route docstrings
2. Add/modify response examples in route decorators
3. Change Pydantic models

To regenerate the static files:

```bash
# Generate both openapi.json and swagger.yaml
python build_openapi.py
```

Then validate the updated schema using the [Swagger Editor](https://editor.swagger.io) and commit the changes.
