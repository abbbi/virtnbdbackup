QEMU_FILE=${TMPDIR}/convert.full.raw
CONVERT_FILE=${TMPDIR}/restored.full.raw
BACKUPSET=${TMPDIR}/testset
RESTORESET=${TMPDIR}/restoreset
VM="vm2"
# lets use an openstack image for testing,
# as the defined virtual machine has way
# too less memory, it wont boot so no changes
# are applied to the image
# VM image is qcow2 so no persistent bitmaps
# are supported, create only copy backups
VM_IMAGE_URL="https://chuangtzu.ftp.acc.umu.se/cdimage/openstack/archive/10.6.0/debian-10.6.0-openstack-amd64.qcow2"
VM_IMAGE="${VM}/vm2-sda.qcow2"

if [ ! -e $VM_IMAGE ]; then
    echo "downloading test image"
    curl $VM_IMAGE_URL > $VM_IMAGE
fi

# convert downloaded image toqcow format supporting persistent
# bitmaps, to allow full backup
if qemu-img info $VM_IMAGE | grep "compat: 0.10" >/dev/null; then
    qemu-img convert -O qcow2 $VM_IMAGE "${VM_IMAGE}.new"
    mv "${VM_IMAGE}.new" "${VM_IMAGE}"
fi

EXTENT_OUTPUT1="Got 866 extents to backup."
EXTENT_OUTPUT2="2147483648 bytes disk size"
EXTENT_OUTPUT3="1394147328 bytes of data extents to backup"

DATA_SIZE="1394147328"
VIRTUAL_SIZE="2147483648"
