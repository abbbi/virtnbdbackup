#!/usr/bin/env python

import os
from setuptools import setup, find_packages
__version__ = "0.1"


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

# the setup
setup(
    name='virtndbbackup',
    version=__version__,
    description='Backup via NBD',
    url='https://github.com/abbbi/virtnbdbackup/',
    author='Michael Ablassmeier',
    author_email='abi@grinser.de',
    license='GPL',
    keywords='libnbd backup libvirt',
    packages=find_packages(exclude=('docs', 'tests', 'env', 'virtnbdbackup.py')),
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
