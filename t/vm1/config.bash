QEMU_FILE=${TMPDIR}/convert.full.raw
CONVERT_FILE=${TMPDIR}/restored.full.raw
BACKUPSET=${TMPDIR}/testset
RESTORESET=${TMPDIR}/restoreset
VM="vm1"
VM_IMAGE="${VM}/vm1-sda.qcow2"


# following outputs are expected for this vm image
DATA_SIZE="6094848"
VIRTUAL_SIZE="52428800"
EXTENT_OUTPUT1="Got 7 extents to backup."
EXTENT_OUTPUT2="${VIRTUAL_SIZE} bytes disk size"
EXTENT_OUTPUT3="${DATA_SIZE} bytes of data extents to backup"

INCTEST="1"
MAPTEST="1"
