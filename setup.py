"""
This is a file to describe the Python module distribution and
helps with installation.

More info on various arguments here:
https://setuptools.readthedocs.io/en/latest/setuptools.html
"""

from setuptools import find_packages, setup

setup(
    name="manifestservice",
    version="0.0.1",
    description="Gen3 service template",
    url="https://github.com/uc-cdis/manifestservice",
    license="Apache",
    packages=find_packages(),
)
