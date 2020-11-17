QEMU_FILE=/tmp/convert.full.raw
CONVERT_FILE=/tmp/restored.full.raw
BACKUPSET=/tmp/testset
RESTORESET=/tmp/restoreset
VM="vm1"

setup() {
    if [ ! -e $BACKUPSET ]; then
        mkdir $BACKUPSET
    fi
}

@test "Setup: Define and start test VM ${VM}" {
    virsh destroy ${VM} || true
    virsh undefine ${VM} --checkpoints-metadata || true
    rm -f /tmp/${VM}-sda.qcow2
    run cp ./${VM}/* /tmp/
    run virsh define /tmp/${VM}.xml
    run virsh start ${VM}
    [ "$status" -eq 0 ]
}
QEMU_FILE=/tmp/convert.full.raw
CONVERT_FILE=/tmp/restored.full.raw
BACKUPSET=/tmp/testset
RESTORESET=/tmp/restoreset
VM="vm1"

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
    run ../virtnbdbackup -q -l copy -d vm1 -o /tmp/extentquery -p
    [[ "$output" =~ "Got 5 extents" ]]
    [[ "$output" =~ "1048576 bytes disk size" ]]
    [[ "$output" =~ "327680 bytes of data extents to backup" ]]
}
@test "Extent: Query extents using extent handler" {
    rm -rf /tmp/extentquery
    run ../virtnbdbackup -l copy -d vm1 -o /tmp/extentquery -p
    [[ "$output" =~ "Got 5 extents" ]]
    [[ "$output" =~ "1048576 bytes disk size" ]]
    [[ "$output" =~ "327680 bytes of data extents to backup" ]]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -t raw -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Creating full provisioned" ]]
}
@test "Compare backup image contents against reference image" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.full.data"
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -q -t raw -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Compare backup image, extents queried via qemu tools" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.full.data"
    [ "$status" -eq 0 ]
}
@test "Backup in stream format"  {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]
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
