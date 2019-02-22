import pytest
import requests
import json as json_utils
from manifest_service import manifests

def test_generate_unique_manifest_filename_basic_date_generation():
	timestamp = "a-b-c"
	users_existing_manifest_files = []
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c.json"

	timestamp = "a-b-c"
	users_existing_manifest_files = ["some-other-file.txt", "another-file.json"]
	filename = manifests.generate_unique_filename_with_timestamp_and_increment(timestamp, users_existing_manifest_files)
	assert filename == "manifest-a-b-c.json"

def test_generate_unique_manifest_filename_if_some_times_are_the_same():
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
	project_access_dict = { }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

	project_access_dict = {'test' : [ 'read-storage' , 'write-storage', 'read' ], 'DEV' : [] }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is True

	project_access_dict = {'test' : [ 'write-storage', 'read' ] , 'abc123' : ['something', 'something-else'] }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

	# You need both read and read-storage to use this service. 
	project_access_dict = {'jenkins' : [ 'read' ] , 'abc123' : ['something', 'something-else'] }
	rv = manifests.does_the_user_have_read_access_on_at_least_one_project(project_access_dict)
	assert rv is False

def test_is_valid_manifest():
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
	data = {
		'api_key' : api_key
	}

	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}

	r = requests.post(fence_hostname + "/user/credentials/api/access_token", json=data, headers=headers)
	json = r.json()
	return json['access_token']

@pytest.mark.skip(reason="This is technically an integration test, because it talks to s3 and Fence")
def test_POST_handles_invalid_json(api_key_one, manifest_service_hostname, fence_hostname):
	cookies = {'access_token' : get_me_an_access_token(api_key_one, fence_hostname) }
	r = requests.post(manifest_service_hostname, data={'a':1}, cookies=cookies)
	assert r.status_code == 400

@pytest.mark.skip(reason="Integration test, because it talks to s3 and Fence")
def test_POST_handles_invalid_manifest_keys(api_key_one, manifest_service_hostname, fence_hostname):
	test_manifest = [{ 'foo' : 44 , "object_id" : 88 }]
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	cookies = {'access_token' : get_me_an_access_token(api_key_one, fence_hostname) }
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 400

@pytest.mark.skip(reason="Integration test, because it talks to s3 and Fence")
def test_POST_successful_manifest_upload(api_key_one, manifest_service_hostname, fence_hostname):
	import random

	random_nums = [ random.randint(1,101) , random.randint(1,101) , random.randint(1,101) , random.randint(1,101) ]
	test_manifest = [{ "subject_id" : random_nums[0] , "object_id" : random_nums[1] }, { "subject_id" : random_nums[2] , "object_id" : random_nums[3] }]
	
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	cookies = {'access_token' : get_me_an_access_token(api_key_one, fence_hostname) }
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 200
	
	json = r.json()
	new_filename = json['filename']
	assert new_filename is not None
	assert type(new_filename) is str
	assert len(new_filename) > 1

	# Check that the new manifest is in the bucket
	r = requests.get(manifest_service_hostname, headers=headers, cookies=cookies)
	assert r.status_code == 200

	json = r.json()
	manifest_files = json['manifests']
	assert type(manifest_files) is list
	assert len(manifest_files) > 0
	assert new_filename in manifest_files

	# Read the body of the manifest and make sure the contents is what we posted
	r = requests.get(manifest_service_hostname + "/file/" + new_filename, headers=headers, cookies=cookies)
	assert r.status_code == 200
	json = r.json()
	response_manifest = json_utils.loads(json['body'])

	assert response_manifest == test_manifest

@pytest.mark.skip(reason="")
def test_GET_fails_if_access_token_missing_or_invalid(manifest_service_hostname, fence_hostname):
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	cookies = {}
	r = requests.get(manifest_service_hostname, headers=headers, cookies=cookies)
	assert r.status_code == 403

	cookies = {'access_token' : 'abc'}
	r = requests.get(manifest_service_hostname, headers=headers, cookies=cookies)
	assert r.status_code == 403

@pytest.mark.skip(reason="")
def test_POST_fails_if_access_token_missing_or_invalid(manifest_service_hostname, fence_hostname):
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}
	test_manifest = [{ "subject_id" : 44 , "object_id" : 88 }]

	cookies = {}
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 403

	cookies = {'access_token' : 'abc'}
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies)
	assert r.status_code == 403

@pytest.mark.skip(reason="Integration test, because it talks to s3 and Fence")
def test_folder_creation_with_multiple_users(api_key_one, api_key_two, manifest_service_hostname, fence_hostname):
	""" 
	In particular, users should never see each others' manifests.
	Or even know that we're making folders for them.
	"""
	
	test_manifest = [{ "subject_id" : 44 , "object_id" : 88 }]
	headers = {'Content-Type': 'application/json', 'Accept':'application/json'}

	# User 1 POST
	cookies_user_1 = {'access_token' : get_me_an_access_token(api_key_one, fence_hostname) }
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies_user_1)
	json = r.json()
	user_1_filename = json['filename']

	# User 2 POST -- notice that we're using the other api_key (from another account)
	cookies_user_2 = {'access_token' : get_me_an_access_token(api_key_two, fence_hostname) }
	r = requests.post(manifest_service_hostname, json=test_manifest, headers=headers, cookies=cookies_user_2)
	json = r.json()
	user_2_filename = json['filename']

	# User 1 GET
	r = requests.get(manifest_service_hostname, headers=headers, cookies=cookies_user_1)
	json = r.json()
	manifest_files = json['manifests']
	assert user_1_filename in manifest_files
	assert user_2_filename not in manifest_files

	# User 2 GET
	r = requests.get(manifest_service_hostname, headers=headers, cookies=cookies_user_2)
	json = r.json()
	manifest_files = json['manifests']
	assert user_2_filename in manifest_files
	assert user_1_filename not in manifest_files