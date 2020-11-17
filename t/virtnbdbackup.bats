QEMU_FILE=/tmp/convert.full.raw
CONVERT_FILE=/tmp/restored.full.raw
BACKUPSET=/tmp/testset
RESTORESET=/tmp/restoreset

setup() {
    if [ ! -e $BACKUPSET ]; then
        mkdir $BACKUPSET
    fi
}

@test "Freeze filesystems within test VM to ensure consistency between test runs" {
    virsh domfsthaw --domain cbt
    virsh domfsfreeze --domain cbt
}
@test "Create reference backup image using qemu-img convert" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -t raw -d cbt -s -o $BACKUPSET
    [ "$status" -eq 0 ]
    run qemu-img convert -f raw nbd://localhost:10809/sda  -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
    run ../virtnbdbackup -t raw -d cbt -k -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -t raw -d cbt -o $BACKUPSET
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Creating full provisioned" ]]
}
@test "Compare backup image contents against reference image" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.full.data"
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -q -t raw -d cbt -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Compare backup image, extents queried via qemu tools" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.full.data"
    [ "$status" -eq 0 ]
}
@test "Backup in stream format"  {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l full -d cbt -o $BACKUPSET
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
@test "Thaw filesystems within test VM" {
    virsh domfsthaw --domain cbt
}
