#!/usr/bin/env python

import os
from setuptools import setup, find_packages
from structure import __version__


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

# the setup
setup(
    name='structure',
    version=__version__,
    description='An demonstration of PyPi.',
    # long_description=read('README'),
    url='https://github.com/kengz/structure',
    author='kengz',
    author_email='kengzwl@gmail.com',
    license='MIT',
    keywords='example pypi tutorial',
    packages=find_packages(exclude=('docs', 'tests', 'env', 'index.py')),
    include_package_data=True,
    install_requires=[
    ],
    extras_require={
    'dev': [],
    'docs': [],
    'testing': [],
    },
    classifiers=[],
    )
