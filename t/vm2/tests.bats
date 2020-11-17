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
VM_IMAGE="https://cdimage.debian.org/cdimage/openstack/archive/10.6.0/debian-10.6.0-openstack-amd64.qcow2"

setup() {
    if [ ! -e $BACKUPSET ]; then
        mkdir $BACKUPSET
    fi
}

@test "Download vm image $VM_IMAGE" {
    curl -L $VM_IMAGE > /tmp/${VM}-sda.qcow2
}

@test "Setup: Define and start test VM ${VM}" {
    virsh destroy ${VM} || true
    virsh undefine ${VM} --checkpoints-metadata || true
    run cp ./${VM}/* /tmp/
    run virsh define /tmp/${VM}.xml
    run virsh start ${VM}
    [ "$status" -eq 0 ]
}

@test "Create reference backup image using qemu-img convert" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -t raw -d $VM -s -o $BACKUPSET
    [ "$status" -eq 0 ]
    run qemu-img convert -f raw nbd://localhost:10809/sda  -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
    run ../virtnbdbackup -t raw -d $VM -k -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Extent: Query extents using qemu tools" {
    rm -rf /tmp/extentquery
    run ../virtnbdbackup -q -l copy -d $VM -o /tmp/extentquery -p
    [[ "$output" =~ "Got 866 extents" ]]
    [[ "$output" =~ "2147483648 bytes disk size" ]]
    [[ "$output" =~ "1394147328 bytes of data extents to backup" ]]
}
@test "Extent: Query extents using extent handler" {
    rm -rf /tmp/extentquery
    run ../virtnbdbackup -l copy -d $VM -o /tmp/extentquery -p
    [[ "$output" =~ "Got 866 extents" ]]
    [[ "$output" =~ "2147483648 bytes disk size" ]]
    [[ "$output" =~ "1394147328 bytes of data extents to backup" ]]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l copy -t raw -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Creating full provisioned" ]]
}
@test "Compare backup image contents against reference image" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.copy.data"
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l copy -q -t raw -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Compare backup image, extents queried via qemu tools" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.copy.data"
    [ "$status" -eq 0 ]
}
@test "Backup in stream format"  {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Dump metadata information" {
    run ../virtnbdrestore -i $BACKUPSET -a dump -o /dev/null
    [[ "$output" =~ "1394147328" ]]
    [[ "$output" =~ "2147483648" ]]
}
@test "Restore stream format"  {
    run ../virtnbdrestore -a restore -i $BACKUPSET -o $RESTORESET
    [ "$status" -eq 0 ]
}
@test "Convert restored qcow2 image to RAW image"  {
    run qemu-img convert -f qcow2 -O raw $RESTORESET/sda $CONVERT_FILE
    [ "$status" -eq 0 ]
}
@test "Compare image contents between converted image and reference image"  {
    run cmp $QEMU_FILE $CONVERT_FILE
    [ "$status" -eq 0 ]
}
