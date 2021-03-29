Test cases, use BATS. Each VM directory contains a special
craftet virtual machine with a given set of disks to be
backed up.

to execute test for certain virtual machine use:

    make vm1.test

to execute all tests:

    make all

using bats directly:

 export TEST=vm1
 ./bats-core/bin/bats tests.bats
