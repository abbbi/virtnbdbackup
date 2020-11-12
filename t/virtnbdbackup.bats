QEMU_FILE=/tmp/convert.full.raw
BACKUP_FILE=/tmp/virtnbdbackup.full.raw

@test "Backup raw using qemu-img convert" {
    rm -f $QEMU_FILE
    run qemu-img convert -f raw nbd://localhost:10809/sda  -O raw $QEMU_FILE
    [ "$status" -eq 0 ]
}
@test "Backup raw using virtnbdbackup" {
    rm -f $BACKUP_FILE
    run ../virtnbdbackup.py -t raw -f $BACKUP_FILE
    [ "$status" -eq 0 ]
}
@test "Compare image contents" {
    run cmp -b $QEMU_FILE $BACKUP_FILE
    [ "$status" -eq 0 ]
}
