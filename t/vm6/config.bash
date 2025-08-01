QEMU_FILE=${TMPDIR}/convert.full.raw
CONVERT_FILE=${TMPDIR}/restored.full.raw
BACKUPSET=${TMPDIR}/testset
RESTORESET=${TMPDIR}/restoreset
VM_IMAGE="vm.qcow2"
VM="vm6"
IMG_URL="https://geo.mirror.pkgbuild.com/images/latest/Arch-Linux-x86_64-basic.qcow2"

# following outputs are expected for this vm image
EXTENT_OUTPUT1="Got 7 extents to backup"
EXTENT_OUTPUT2="1048576 bytes"
EXTENT_OUTPUT3="327680 bytes"

DATA_SIZE="327680"
VIRTUAL_SIZE="1048576"
