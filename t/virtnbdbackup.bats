QEMU_FILE=/tmp/convert.full.raw
BACKUP_FILE=/tmp/virtnbdbackup.full.raw
BACKUP_FILE_Q=/tmp/virtnbdbackupq.full.raw

@test "Backup raw using qemu-img convert" {
    rm -f $QEMU_FILE
    run qemu-img convert -f raw nbd://localhost:10809/sda  -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -f $BACKUP_FILE
    run ../virtnbdbackup -t raw -f $BACKUP_FILE
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -f $BACKUP_FILE_Q
    run ../virtnbdbackup -q -t raw -f $BACKUP_FILE_Q
    [ "$status" -eq 0 ]
}
@test "Compare image contents for backup with extenthandler" {
    run cmp -b $QEMU_FILE $BACKUP_FILE
    [ "$status" -eq 0 ]
}
@test "Compare image contents for backup with qemu extents" {
    run cmp -b $QEMU_FILE $BACKUP_FILE_Q
    [ "$status" -eq 0 ]
}
