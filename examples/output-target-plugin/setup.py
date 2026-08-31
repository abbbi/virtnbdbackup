#!/usr/bin/env python3
"""Packaging for the virtnbdbackup example output target plugin."""

from setuptools import find_packages, setup


setup(
    name="virtnbdbackup-example-output-target",
    version="0.1.0",
    description="Example output target plugin for virtnbdbackup",
    packages=find_packages(),
    entry_points={
        "virtnbdbackup.output_targets": [
            "example-directory = virtnbdbackup_example_target:ExampleDirectoryTarget"
        ]
    },
)
