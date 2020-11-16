QEMU_FILE=/tmp/convert.full.raw
BACKUPSET=/tmp/testset

setup() {
    if [ ! -e $BACKUPSET ]; then
        mkdir $BACKUPSET
    fi
}

@test "Backup raw using qemu-img convert" {
    run ../virtnbdbackup -t raw -d cbt -s -o $BACKUPSET
    [ "$status" -eq 0 ]
    run qemu-img convert -f raw nbd://localhost:10809/sda  -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
    run ../virtnbdbackup -t raw -d cbt -k -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -rf /tmp/testset
    run ../virtnbdbackup -t raw -d cbt -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Compare image contents for backup with extenthandler" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.copy.data"
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -rf /tmp/testset
    run ../virtnbdbackup -q -t raw -d cbt -o $BACKUPSET
    [ "$status" -eq 0 ]
}
@test "Compare image contents for backup with qemu extents" {
    run cmp -b $QEMU_FILE "${BACKUPSET}/sda.copy.data"
    [ "$status" -eq 0 ]
}
