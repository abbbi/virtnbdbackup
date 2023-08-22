#!/bin/bash
set -e

mkdir -p ../dist
mkdir -p ../dist/debian
mkdir -p ../dist/rhel8
mkdir -p ../dist/rhel9

export VAGRANT_CWD=$(pwd)/debian/
vagrant up && vagrant destroy -f

export VAGRANT_CWD=$(pwd)/rhel8/
vagrant up && vagrant destroy -f

export VAGRANT_CWD=$(pwd)/rhel9/
vagrant up && vagrant destroy -f
