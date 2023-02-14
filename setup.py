#!/usr/bin/env python3
"""Setup virtnbdbackup"""
from setuptools import setup, find_packages

import libvirtnbdbackup

with open("requirements.txt") as f:
    install_requires = f.read().splitlines()

setup(
    name="virtnbdbackup",
    version=libvirtnbdbackup.__version__,
    description="Backup utility for libvirt",
    url="https://github.com/abbbi/virtnbdbackup/",
    author="Michael Ablassmeier",
    author_email="abi@grinser.de",
    license="GPL",
    keywords="libnbd backup libvirt",
    packages=find_packages(exclude=("docs", "tests", "env")),
    include_package_data=True,
    scripts=["virtnbdbackup", "virtnbdrestore", "virtnbdmap", "virtnbd-nbdkit-plugin"],
    install_requires=install_requires,
    extras_require={
        "dev": [],
        "docs": [],
        "testing": [],
    },
    classifiers=[],
)
