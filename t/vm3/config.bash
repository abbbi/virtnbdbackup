QEMU_FILE=${TMPDIR}/convert.full.raw
CONVERT_FILE=${TMPDIR}/restored.full.raw
BACKUPSET=${TMPDIR}/testset
RESTORESET=${TMPDIR}/restoreset
VM="vm3"
VM_IMAGE="${VM}/vm3-*.qcow2"


# following outputs are expected for this vm image
if [ -z $GITHUB_JOB ]; then
    EXTENT_OUTPUT1="Got 7 extents to backup."
    EXTENT_OUTPUT2="1048576 bytes"
    EXTENT_OUTPUT3="327680 bytes"

    DATA_SIZE="327680"
else
    EXTENT_OUTPUT1="Got 5 extents to backup."
    EXTENT_OUTPUT2="1048576 bytes"
    EXTENT_OUTPUT3="131072 bytes"

    DATA_SIZE="131072"
fi

VIRTUAL_SIZE="1048576"
