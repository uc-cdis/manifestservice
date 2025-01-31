import collections

import yaml
from flasgger import Flasgger, Swagger
from openapi.app_info import app_info
from yaml.representer import Representer

from manifestservice.api import app


def write_swagger():
    """
    Generate the Swagger documentation and store it in a file.
    """
    yaml.add_representer(collections.defaultdict, Representer.represent_dict)
    outfile = "openapi/swagger.yaml"
    with open(outfile, "w") as swagger_file:
        data = Flasgger.get_apispecs(swagger)
        yaml.dump(data, swagger_file, default_flow_style=False)
        print("Generated docs")


if __name__ == "__main__":
    try:
        with app.app_context():
            swagger = Swagger(app, template=app_info)
            write_swagger()
    except Exception as err:
        print(f"Could not generate docs: {err}")
