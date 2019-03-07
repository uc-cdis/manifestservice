import pytest
import requests
import json as json_utils

from manifest_service import manifests

from manifest_service.api import create_app

mocks = {}

@pytest.fixture
def app(mocker):
	test_user = {
		'context': {
			'user': {'policies': ['data_upload', 'programs.test-read-storage', 'programs.test-read'], 
			'google': {'proxy_group': None}, 
			'is_admin': True, 
			'name': 'example@uchicago.edu', 
			'projects': 
				{'test': 
					['read-storage', 'read', 'create', 'write-storage', 'upload', 'update', 'delete'] 
				}
			}
		}, 	
		'aud': ['data', 'user', 'fence', 'openid'], 
		'sub': '18'
	}

	mocks['validate_request'] = mocker.patch("manifest_service.manifests.validate_request", return_value=test_user)

	mocks['list_files_in_bucket'] = mocker.patch("manifest_service.manifests.list_files_in_bucket", return_value=[{ 'filename':'manifest-a-b-c.json' } ])

	# mocks['add_manifest_to_bucket'] = mocker.patch("manifest_service.manifests.add_manifest_to_bucket", return_value='manifest-a-b-c.json')

	#mocks['boto3'] = mocker.patch("manifest_service.manifests.boto3.Session", return_value="foo")
	#mocks['boto3.Session'] = mocker.patch("manifest_service.manifests.boto3.Session")
	#mocks['s3'] = mocker.patch("manifest_service.manifests.s3")
	mocks['s3.Object'] = mocker.patch("manifest_service.manifests.s3.Object")

	mocks['get_file_contents'] = mocker.patch("manifest_service.manifests.get_file_contents", return_value='')

	app = create_app()
	return app

def test_generate_unique_manifest_filename_basic_date_generation():
	"""
	Tests that the generate_unique_filename_with_timestamp_and_increment() function
	generates a unique filename containing the given timestamp, based on the files in the
	user's bucket. 
	"""
	timestamp = "a-b-c"
	users_existing_manifest_files = []
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c.json"

	timestamp = "a-b-c"
	users_existing_manifest_files = ["some-other-file.txt", "another-file.json"]
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c.json"

	# Case 1: One collision
	timestamp = "a-b-c"
	users_existing_manifest_files = ["manifest-a-b-c.json"]
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c-1.json"

	# Case 2: Two collisions
	timestamp = "a-b-c"
	users_existing_manifest_files = ["manifest-a-b-c.json", "manifest-a-b-c-1.json"]
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c-2.json"

	# Case 3: Three collisions. This should never ever happen but eh might as well test it. 
	timestamp = "a-b-c"
	users_existing_manifest_files = ["manifest-a-b-c.json", "manifest-a-b-c-1.json",  "manifest-a-b-c-2.json"]
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c-3.json"

def test_does_the_user_have_read_access_on_at_least_one_project():
	"""
	Tests that the function does_the_user_have_read_access_on_at_least_one_project()
	provides the correct value for different arborist user_info inputs.
	"""
	project_access_dict = { }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

	project_access_dict = {'context' : { 'user' : { 'projects' : {'test' : [ 'read-storage' , 'write-storage', 'read' ], 'DEV' : [] } } } }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is True

	project_access_dict = {'context' : { 'user' : { 'projects' : {'test' : [ 'write-storage', 'read' ] , 'abc123' : ['something', 'something-else'] } } } }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

	# You need both read and read-storage to use this service. 
	project_access_dict = {'context' : { 'user' : { 'projects' : {'jenkins' : [ 'read' ] , 'abc123' : ['something', 'something-else'] } } } }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

def test_is_valid_manifest():
	"""
	Tests that the function is_valid_manifest() correctly determines
	if the input manifest string is valid.
	"""
	test_manifest = [{ "foo" : 44 }]
	is_valid, err_message = manifests.is_valid_manifest(test_manifest)
	assert is_valid is False

	test_manifest = [{ "foo" : 44 , "bar" : 88 }]
	is_valid, err_message = manifests.is_valid_manifest(test_manifest)
	assert is_valid is False

	test_manifest = [{ "foo" : 44 , "object_id" : 88 }]
	is_valid, err_message = manifests.is_valid_manifest(test_manifest)
	assert is_valid is False

	test_manifest = [{ "subject_id" : 44 , "object_id" : 88 }]
	is_valid, err_message = manifests.is_valid_manifest(test_manifest)
	assert is_valid is True

	test_manifest = [{ "object_id" : 88 }]
	is_valid, err_message = manifests.is_valid_manifest(test_manifest)
	assert is_valid is True

def get_me_an_access_token(api_key, fence_hostname):
	"""
	Just a helper function that gets an access token for use with Fence
	based on the optional api key passed into pytest. This access token is
	used to facilitate the test functions that make requests to the manifest_service.
	(Without an access token, all requests to the service will come back 403s).
	"""
	data = {
		'api_key' : api_key
	}

	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}

	r = client.post(fence_hostname + "/user/credentials/api/access_token", json=data, headers=headers)
	json = r.json()
	return json['access_token']

def test_POST_handles_invalid_json(client):
	r = client.post("/", data={'a':1})
	assert r.status_code == 400

def test_POST_handles_invalid_manifest_keys(client):
	test_manifest = [{ 'foo' : 44 , "object_id" : 88 }]
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	r = client.post("/", json=test_manifest, headers=headers)
	assert r.status_code == 400

def test_POST_successful_manifest_upload(client):
	import random

	random_nums = [ random.randint(1,101) , random.randint(1,101) , random.randint(1,101) , random.randint(1,101) ]
	test_manifest = [{ "subject_id" : random_nums[0] , "object_id" : random_nums[1] }, { "subject_id" : random_nums[2] , "object_id" : random_nums[3] }]
	
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	r = client.post("/", data=json_utils.dumps(test_manifest), headers=headers)
	
	assert r.status_code == 200
	assert mocks['validate_request'].call_count == 1
	assert mocks['s3.Object'].call_count == 1
	assert mocks['list_files_in_bucket'].call_count == 1	# To generate a unique filename, the code should check the bucket
	assert mocks['get_file_contents'].call_count == 0

	json = r.json
	new_filename = json['filename']
	
	assert new_filename is not None
	assert type(new_filename) is str
	
	r = client.get("/", headers=headers)
	assert r.status_code == 200
	assert mocks['validate_request'].call_count == 2
	assert mocks['s3.Object'].call_count == 1
	assert mocks['list_files_in_bucket'].call_count == 2
	assert mocks['get_file_contents'].call_count == 0

	json = r.json
	manifest_files = json['manifests']
	assert type(manifest_files) is list

	r = client.get("/file/" + new_filename, headers=headers)
	assert r.status_code == 200
	assert mocks['validate_request'].call_count == 3
	assert mocks['s3.Object'].call_count == 1
	assert mocks['list_files_in_bucket'].call_count == 2
	assert mocks['get_file_contents'].call_count == 1