"""
This is a file to describe the Python module distribution and
helps with installation.

More info on various arguments here:
https://setuptools.readthedocs.io/en/latest/setuptools.html
"""
from setuptools import setup, find_packages


setup(
    name="manifest_service",
    version="0.0.1",
    description="Gen3 service template",
    url="https://github.com/uc-cdis/manifest_service",
    license="Apache",
    packages=find_packages(),

)
