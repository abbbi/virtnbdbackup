QEMU_FILE=${TMPDIR}/convert.full.raw
CONVERT_FILE=${TMPDIR}/restored.full.raw
BACKUPSET=${TMPDIR}/testset
RESTORESET=${TMPDIR}/restoreset
VM="vm4"
VM_IMAGE="${VM}/vm4-*.qcow2"


if [ -z $GITHUB_JOB ]; then
# following outputs are expected for this vm image
    EXTENT_OUTPUT1="Got 7 extents to backup"
    EXTENT_OUTPUT2="1048576 bytes disk size"
    EXTENT_OUTPUT3="327680 bytes of data extents to backup"
    DATA_SIZE="327680"
else
    EXTENT_OUTPUT1="Got 5 extents to backup"
    EXTENT_OUTPUT2="1048576 bytes"
    EXTENT_OUTPUT3="131072"
    DATA_SIZE="131072"
fi

VIRTUAL_SIZE="1048576"
HAS_RAW=1
