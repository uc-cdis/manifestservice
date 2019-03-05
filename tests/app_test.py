import pytest
import requests
import json as json_utils

from manifest_service import manifests

from manifest_service.api import create_app

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

	mocker.patch("manifest_service.manifests.validate_request", return_value=test_user)

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

@pytest.mark.skip(reason="This is an integration test because it requires s3 credentials. I would rather keep this good test intact than mock s3.")
def test_POST_successful_manifest_upload(client):
	import random

	random_nums = [ random.randint(1,101) , random.randint(1,101) , random.randint(1,101) , random.randint(1,101) ]
	test_manifest = [{ "subject_id" : random_nums[0] , "object_id" : random_nums[1] }, { "subject_id" : random_nums[2] , "object_id" : random_nums[3] }]
	
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	r = client.post("/", data=json_utils.dumps(test_manifest), headers=headers)
	print(r.data)
	assert r.status_code == 200
	
	json = r.json
	new_filename = json['filename']
	assert new_filename is not None
	assert type(new_filename) is str
	assert len(new_filename) > 1

	# Check that the new manifest is in the bucket
	r = client.get("/", headers=headers)
	assert r.status_code == 200

	json = r.json
	manifest_files = json['manifests']
	assert type(manifest_files) is list
	assert len(manifest_files) > 0
	assert new_filename in manifest_files

	# Read the body of the manifest and make sure the contents is what we posted
	r = client.get("/file/" + new_filename, headers=headers)
	assert r.status_code == 200
	json = r.json
	response_manifest = json_utils.loads(json['body'])

	assert response_manifest == test_manifest

@pytest.mark.skip(reason="This test is difficult to automate and will be tested by an integration test anyway.")
def test_GET_fails_if_access_token_missing_or_invalid(manifest_service_hostname):
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	cookies = {}
	r = client.get("/", headers=headers)
	assert r.status_code == 403

	cookies = {'access_token' : 'abc'}
	r = client.get("/", headers=headers)
	assert r.status_code == 403

@pytest.mark.skip(reason="This test is difficult to automate and will be tested by an integration test anyway.")
def test_POST_fails_if_access_token_missing_or_invalid(client):
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	test_manifest = [{ "subject_id" : 44 , "object_id" : 88 }]

	cookies = {}
	r = client.post("/", json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 403

	cookies = {'access_token' : 'abc'}
	r = client.post("/", json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 403

@pytest.mark.skip(reason="This test is difficult to automate and will be tested by an integration test anyway.")
def test_folder_creation_with_multiple_users(client, api_key_one, api_key_two, fence_hostname):
	""" 
	In particular, users should never see each others' manifests.
	Or even know that we're making folders for them.
	"""
	
	test_manifest = [{ "subject_id" : 44 , "object_id" : 88 }]
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}

	# User 1 POST
	cookies_user_1 = {'access_token' : get_me_an_access_token(api_key_one, fence_hostname) }
	r = client.post("/", json=test_manifest, headers=headers, cookies=cookies_user_1)
	json = r.json()
	user_1_filename = json['filename']

	# User 2 POST -- notice that we're using the other api_key (from another account)
	cookies_user_2 = {'access_token' : get_me_an_access_token(api_key_two, fence_hostname) }
	r = client.post("/", json=test_manifest, headers=headers, cookies=cookies_user_2)
	json = r.json()
	user_2_filename = json['filename']

	# User 1 GET
	r = client.get("/", headers=headers, cookies=cookies_user_1)
	json = r.json()
	manifest_files = json['manifests']
	assert user_1_filename in manifest_files
	assert user_2_filename not in manifest_files

	# User 2 GET
	r = client.get("/", headers=headers, cookies=cookies_user_2)
	json = r.json()
	manifest_files = json['manifests']
	assert user_2_filename in manifest_files
	assert user_1_filename not in manifest_files