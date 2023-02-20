# Manifest Service
### Overview
This service handles reading from and writing to a user's s3 folder containing their manifests. A manifest is a JSON file that lists records a researcher may be interested in analyzing. This service stores a manifest to a user folder in an s3 bucket and delivers it for later use, such as when the researcher wants to mount the manifest in their workspace. If the "prefix" config variable is set, user folders will be stored in a directory of that name within the s3 bucket.

Manifest files should contain JSON of the form

    [
      {
        "object_id": "757508f5-2697-4700-a69f-89d173a4c514",
        "subject_id": "da6a14a0-6498-4941-a1b2-bbe45a2ccac2"
      },
      {
        "object_id": "835db5c6-5cc8-4d70-a3b2-9a18ad4912cd",
        "subject_id": "da6a14a0-6498-4941-a1b2-bbe45a2ccac2"
      },
      ...
    ]

### Endpoints

For all endpoints, the request must contain an Authorization header with an access_token. The user needs read access and read-storage access
on at least one project in order to use this service.

Lists a user's manifests:

    GET /
    Returns: { "manifests" : [ { "filename" : "manifest-2019-02-27T11-44-20.548126.json", "last_modified" : "2019-02-27 17:44:21" }, ... ] }

Create a manifest file in the user's folder:

    POST /
    Post body: The contents of the manifest.json file to be created.
    Returns: { "filename" : "manifest-2019-03-09T21-47-04.041499.json" }

Read the contents of a manifest file in the user's folder:

    GET /file/<filename.json>
    Returns: { "body" : "the-body-of-the-manifest-file-as-a-string" }

Lists a user's cohorts:

    GET /cohorts
    Returns: { "cohorts" : [ { "filename" : "5183a350-9d56-4084-8a03-6471cafeb7fe", "last_modified" : "2019-02-27 17:44:21" }, ... ] }

Create a cohort GUID in the user's folder:

    POST /cohorts
    Post body: { "guid": "5183a350-9d56-4084-8a03-6471cafeb7fe" }
    Returns: { "filename" : "5183a350-9d56-4084-8a03-6471cafeb7fe" }

On failure, the above endpoints all return JSON in the form

    { "error" : "error-message" }


### Running the service locally
If you want to run this service locally, fill out the config.json file with the correct values and then run:

    poetry shell
    poetry install
    python3 run.py

And then GET and POST to http://localhost:5000/

You'll need AWS credentials in your environment to run this locally.

### Quickstart with Helm

You can now deploy individual services via Helm!

If you are looking to deploy all Gen3 services, that can be done via the Gen3 Helm chart.
Instructions for deploying all Gen3 services with Helm can be found [here](https://github.com/uc-cdis/gen3-helm#readme).

To deploy the manifestservice service:
```bash
helm repo add gen3 https://helm.gen3.org
helm repo update
helm upgrade --install gen3/manifestservice
```
These commands will add the Gen3 helm chart repo and install the manifestservice service to your Kubernetes cluster.

Deploying manifestservice this way will use the defaults that are defined in this [values.yaml file](https://github.com/uc-cdis/gen3-helm/blob/master/helm/manifestservice/values.yaml)
You can learn more about these values by accessing the manifestservice [README.md](https://github.com/uc-cdis/gen3-helm/blob/master/helm/manifestservice/README.md)

If you would like to override any of the default values, simply copy the above values.yaml file into a local file and make any changes needed.

To deploy the service independant of other services (for testing purposes), you can set the .postgres.separate value to "true". This will deploy the service with its own instance of Postgres:
```bash
  postgres:
    separate: true
```

You can then supply your new values file with the following command:
```bash
helm upgrade --install gen3/manifestservice -f values.yaml
```

If you are using Docker Build to create new images for testing, you can deploy them via Helm by replacing the .image.repository value with the name of your local image.
You will also want to set the .image.pullPolicy to "never" so kubernetes will look locally for your image.
Here is an example:
```bash
image:
  repository: <image name from docker image ls>
  pullPolicy: Never
  # Overrides the image tag whose default is the chart appVersion.
  tag: ""
```

Re-run the following command to update your helm deployment to use the new image:
```bash
helm upgrade --install gen3/manifestservice
```

You can also store your images in a local registry. Kind and Minikube are popular for their local registries:
- https://kind.sigs.k8s.io/docs/user/local-registry/
- https://minikube.sigs.k8s.io/docs/handbook/registry/#enabling-insecure-registries
