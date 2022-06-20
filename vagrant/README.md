Build rpm/debian packages via varant.

For building the RedHat/Alma/Rocky variant:

 export VAGRANT_CWD=rhel
 vagrant up

For building the debian version:

 export VAGRANT_CWD=debian
 vagrant up

Resulting rpm and debian packages will be placed
in $VAGRANT_CWD.
