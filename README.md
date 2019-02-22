# Manifest Service
### Overview
This service handles reading from and writing to a user's s3 folder containing their manifests. A manifest is a JSON file that lists records a researcher may be interested in analyzing. This service stores a manifest to a user folder in an s3 bucket and delivers it for later use, such as when the researcher wants to mount the manifest in their workspace. 

### Endpoints

For all endpoints, the request cookie should contain an access_token. The user needs read access and read-storage access
on at least one project in order to use this service.

Lists a user's manifests: 

    GET /
    Returns: { "manifests" : [ "filename-1.json", "filename-2.json", ... ] }

Create a manifest file in the user's folder:

    POST /
    Post body: The contents of the manifest.json file to be created.
    Returns: { "filename" : "the-timestamped-filename-generated-by-the-service.json" }

Read the contents of a manifest file in the user's folder:

    GET /file/<filename.json>
    Returns: { "body" : "the-body-of-the-manifest-file-as-a-string" }

On failure, the above endpoints all return JSON in the form 
    
    { "error" : "error-message" }

### Running the service locally
If you want to run this service locally, fill out manifest_service/dev_settings.py with the correct values and then run:

    virtualenv -p python3 ~/manifest_service_env
    source ~/manifest_service_env/bin/activate
    pip3 install  -r requirements.txt
    python3 run.py

And then GET and POST to http://localhost:5000/

You'll need AWS credentials in your environment to run this locally.