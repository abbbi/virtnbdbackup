QEMU_FILE=/tmp/convert.full.raw
CONVERT_FILE=/tmp/restored.full.raw
BACKUPSET=/tmp/testset
RESTORESET=/tmp/restoreset
VM="vm4"
VM_IMAGE="${VM}/vm4-sda.qcow2"


# following outputs are expected for this vm image
EXTENT_OUTPUT1="Got 5 extents"
EXTENT_OUTPUT2="1048576 bytes disk size"
EXTENT_OUTPUT3="327680 bytes of data extents to backup"

DATA_SIZE="327680"
VIRTUAL_SIZE="1048576"
