if [ -z "$TEST" ]; then
    echo ""
    echo "Missing required test env" >&2
    echo "export TEST=<dir> to run specified tests" >&2
    echo ""
    exit
fi

load $TEST/config.bash

@test "Setup / download vm image $VM_IMAGE to /tmp/" {
    cp ${VM_IMAGE} /tmp/
}

@test "Setup: Define and start test VM ${VM}" {
    virsh destroy ${VM} || true
    virsh undefine ${VM} --remove-all-storage --checkpoints-metadata || true
    cp ${VM}/${VM}.xml /tmp/
    run virsh define /tmp/${VM}.xml
    run virsh start ${VM}
    [ "$status" -eq 0 ]
}
@test "Create reference backup image using qemu-img convert to $BACKUPSET" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -t raw -d $VM -s -o $BACKUPSET --socketfile /tmp/sock
    [ "$status" -eq 0 ]
    run qemu-img convert -f raw nbd+unix:///sda?socket=/tmp/sock -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
    run ../virtnbdbackup -t raw -d $VM -k -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Extent: Query extents using qemu tools" {
    rm -rf /tmp/extentquery
    run ../virtnbdbackup -q -l copy -d $VM -o /tmp/extentquery -p
    [[ "$output" =~ "$EXTENT_OUTPUT1" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT2" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT3" ]]
}
@test "Extent: Query extents using extent handler" {
    rm -rf /tmp/extentquery
    run ../virtnbdbackup -l copy -d $VM -o /tmp/extentquery -p
    [[ "$output" =~ "$EXTENT_OUTPUT1" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT2" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT3" ]]
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
toOut() {
    # for some reason bats likes to hijack stdout which results
    # in data being read into memory  ... helper function works
    # around this issue.
    ../virtnbdbackup -l copy -d $VM -i sda -o - > /tmp/stdout.sda
}
@test "Backup in stream format,single disk write to stdout"  {
    rm -f /tmp/stdout.sda
    export PYTHONUNBUFFERED=True
    run toOut
    [ "$status" -eq 0 ]
    [ -e /tmp/stdout.sda ]
}
@test "Dump metadata information" {
    run ../virtnbdrestore -i $BACKUPSET -a dump -o /dev/null
    [[ "$output" =~ "$DATA_SIZE" ]]
    [[ "$output" =~ "$VIRTUAL_SIZE" ]]
}
@test "Restore stream format"  {
    run ../virtnbdrestore -a restore -i $BACKUPSET -o $RESTORESET
    [[ "$output" =~ "End of stream" ]]
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

# compression
@test "Backup in stream format: with and without compression, restore both and compare results"  {
    BACKUPSET_COMPRESSED="/tmp/testset_compressed"

    RESTOREDIR="/tmp/restore_uncompressed"
    RESTOREDIR_COMPRESSED="/tmp/restore_compressed"

    rm -rf $BACKUPSET $BACKUPSET_COMPRESSED

    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET
    [ "$status" -eq 0 ]

    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET_COMPRESSED --compress
    [ "$status" -eq 0 ]

    run ../virtnbdrestore -a restore -i $BACKUPSET_COMPRESSED -o $RESTOREDIR -n -v
    [ "$status" -eq 0 ]

    run ../virtnbdrestore -a restore -i $BACKUPSET_COMPRESSED -o $RESTOREDIR_COMPRESSED -n -v
    [ "$status" -eq 0 ]

    run cmp /tmp/restore_uncompressed/sda /tmp/restore_compressed/sda
    [ "$status" -eq 0 ]

    rm -rf $RESTOREDIR $RESTOREDIR_COMPRESSED
}

# test for incremental backup

@test "Setup: Prepare test for incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    command -v guestmount || exit 1
    rm -rf /tmp/inctest
}
@test "Backup: create full backup" {
    [ -z $INCTEST ] && skip "skipping"
    run ../virtnbdbackup -d $VM -l full -o /tmp/inctest
    [ "$status" -eq 0 ]
}
@test "Setup: destroy VM" {
    [ -z $INCTEST ] && skip "skipping"
    run virsh destroy $VM
    [ "$status" -eq 0 ]
}
@test "Setup: mount disk via guestmount and create file" {
    [ -z $INCTEST ] && skip "skipping"
    run guestmount -d $VM -m /dev/sda1  /mnt/
    [ "$status" -eq 0 ]
    echo incfile > /mnt/incfile
    run umount /mnt/
    [ "$status" -eq 0 ]
}
@test "Setup: start VM after creating file" {
    [ -z $INCTEST ] && skip "skipping"
    sleep 5 # not sure why..
    run virsh start $VM
    [ "$status" -eq 0 ]
}
@test "Backup: create incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    run ../virtnbdbackup -d $VM -l inc -o /tmp/inctest
    [ "$status" -eq 0 ]
}
@test "Restore: restore data and check if file from incremental backup exists" {
    [ -z $INCTEST ] && skip "skipping"
    rm -rf /tmp/RESTOREINC/
    run ../virtnbdrestore -a restore -i /tmp/inctest/ -o /tmp/RESTOREINC/
    [ "$status" -eq 0 ]
    run guestmount -a /tmp/RESTOREINC/sda -m /dev/sda1  /mnt
    [ "$status" -eq 0 ]
    [ -e /mnt/incfile ]
    run umount /mnt
    [ "$status" -eq 0 ]
}
