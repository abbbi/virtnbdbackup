Test cases, use BATS. Each VM directory contains a special crafted virtual
machine with a given set of disks to be backed up. The virtual machines are
started but do not alter their filesystems while running, to ensure the same
data-sizes are reported for each test.

If files within virtual machine should be changed, vm is destroyed and disks
are mounted via guestfs tools.

Tests will only correctly run on centos 8 with libvirt from the advanced
virtualization stream, because virtual machine xml definition includes
some specific settings.

To execute test for certain virtual machine use:

    make vm1.test

to execute all tests:

    make all

using bats directly:

 export TEST=vm1
 ./bats-core/bin/bats tests.bats
