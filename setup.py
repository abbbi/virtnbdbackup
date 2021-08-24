#!/usr/bin/env python3
import os
from setuptools import setup, find_packages

import libvirtnbdbackup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="virtnbdbackup",
    version=libvirtnbdbackup.__version__,
    description="Backup via NBD",
    url="https://github.com/abbbi/virtnbdbackup/",
    author="Michael Ablassmeier",
    author_email="abi@grinser.de",
    license="GPL",
    keywords="libnbd backup libvirt",
    packages=find_packages(exclude=("docs", "tests", "env")),
    include_package_data=True,
    install_requires=[],
    scripts=["virtnbdbackup", "virtnbdrestore"],
    extras_require={
        "dev": [],
        "docs": [],
        "testing": [],
    },
    classifiers=[],
)
