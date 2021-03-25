if [ -z "$TEST" ]; then
    echo ""
    echo "Missing required test env" >&2
    echo "export TEST=<dir> to run specified tests" >&2
    echo ""
    exit
fi

load $TEST/config.bash

@test "Setup / download vm image $VM_IMAGE_URL" {
    if [ ! ls "$VM_IMAGE" > /dev/null 2>&1 ]; then
        curl -L $VM_IMAGE_URL > ${VM_IMAGE}
    fi
    cp ${VM_IMAGE} /tmp/
}
@test "Setup: Define and start test VM ${VM}" {
    virsh destroy ${VM} || true
    virsh undefine ${VM} --checkpoints-metadata || true
    cp ${VM}/${VM}.xml /tmp/
    run virsh define /tmp/${VM}.xml
    run virsh start ${VM}
    [ "$status" -eq 0 ]
}
@test "Create reference backup image using qemu-img convert to $BACKUPSET" {
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
    # in data beeing read into memory  ... helper function works
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
