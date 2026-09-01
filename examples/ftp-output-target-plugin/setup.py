#!/usr/bin/env python3
"""Packaging for the virtnbdbackup FTP output target plugin."""

from setuptools import find_packages, setup


setup(
    name="virtnbdbackup-ftp-output-target",
    version="0.1.0",
    description="FTP output target plugin for virtnbdbackup",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "virtnbdbackup.output_targets": [
            "ftp = virtnbdbackup_ftp_target:FTPOutputTarget"
        ]
    },
)
