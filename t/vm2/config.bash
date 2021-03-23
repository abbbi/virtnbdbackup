QEMU_FILE=/tmp/convert.full.raw
CONVERT_FILE=/tmp/restored.full.raw
BACKUPSET=/tmp/testset2
RESTORESET=/tmp/restoreset2
VM="vm2"
# lets use an openstack image for testing,
# as the defined virtual machine has way
# too less memory, it wont boot so no changes
# are applied to the image
# VM image is qcow2 so no persistent bitmaps
# are supported, create only copy backups
VM_IMAGE_URL="https://cdimage.debian.org/cdimage/openstack/archive/10.6.0/debian-10.6.0-openstack-amd64.qcow2"
VM_IMAGE="debian-10.6.0-openstack-amd64.qcow2"

EXTENT_OUTPUT1="Got 866 extents"
EXTENT_OUTPUT2="2147483648 bytes disk size"
EXTENT_OUTPUT3="1394147328 bytes of data extents to backup"

DATA_SIZE="1394147328"
VIRTUAL_SIZE="2147483648"
