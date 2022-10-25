#!/bin/bash
set -e
help2man -n "backup utility for libvirt" ./virtnbdbackup -N > man/virtnbdbackup.1
help2man -n "restore utility for libvirt" ./virtnbdrestore -N > man/virtnbdrestore.1
help2man -n "map virtnbdbackup image files to nbd devices" ./virtnbdmap -N > man/virtnbdmap.1
