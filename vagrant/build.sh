#!/bin/bash
set -e
export VAGRANT_CWD=$(pwd)/debian/
vagrant up && vagrant destroy -f

export VAGRANT_CWD=$(pwd)/rhel/
vagrant up && vagrant destroy -f
