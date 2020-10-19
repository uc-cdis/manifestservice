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

On failure, the above endpoints all return JSON in the form

    { "error" : "error-message" }

### Running the service locally
If you want to run this service locally, fill out the config.json file with the correct values and then run:

    pipenv install --skip-lock --dev
    python3 run.py

And then GET and POST to http://localhost:5000/

You'll need AWS credentials in your environment to run this locally.
