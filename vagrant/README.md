Build rpm/Debian packages via vagrant.

For building the Red Hat/Alma/Rocky variant:

```
 export VAGRANT_CWD=rhel8
 vagrant up
 export VAGRANT_CWD=rhel9
 vagrant up
```

For building the Debian version:

```
 export VAGRANT_CWD=debian
 vagrant up
```

Resulting rpm and Debian packages will be placed
in $VAGRANT_CWD.
