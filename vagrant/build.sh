#!/bin/bash
set -e
export VAGRANT_CWD=$(pwd)/debian/
vagrant up && vagrant destroy -f

export VAGRANT_CWD=$(pwd)/rhel8/
vagrant up && vagrant destroy -f

export VAGRANT_CWD=$(pwd)/rhel9/
vagrant up && vagrant destroy -f
