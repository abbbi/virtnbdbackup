if [ -z "$TEST" ]; then
    echo ""
    echo "Missing required test env" >&2
    echo "export TEST=<dir> to run specified tests" >&2
    echo ""
    exit
fi

if [ -z "$TMPDIR" ]; then
    export TMPDIR=$(mktemp -d)
    chmod go+rwx $TMPDIR
fi
load $TEST/config.bash

setup() {
 aa-teardown >/dev/null
}

@test "Setup / download vm image $VM_IMAGE to ${TMPDIR}/" {
    cp ${VM_IMAGE} ${TMPDIR}
}

@test "Setup: Define and start test VM ${VM}" {
    virsh destroy ${VM} || true
    echo "output = ${output}"
    virsh undefine ${VM} --remove-all-storage --checkpoints-metadata || true
    echo "output = ${output}"
    cp ${VM}/${VM}.xml ${TMPDIR}/
    sed -i "s|__TMPDIR__|${TMPDIR}|g" ${TMPDIR}/${VM}.xml
    run virsh define ${TMPDIR}/${VM}.xml
    echo "output = ${output}"
    run virsh start ${VM}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    echo "output = ${output}"
}

@test "Start backup job and nbd endpoint to create reference image" {
    if [ ! -z $HAS_RAW ]; then
        OPT="--raw"
        echo "Raw disk attached Additional options: $OPT" >&3
    fi
    rm -rf $BACKUPSET
    run ../virtnbdbackup -t raw $OPT -d $VM -s -o $BACKUPSET --socketfile ${TMPDIR}/sock
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Create reference backup image using qemu-img convert to $BACKUPSET" {
    for disk in $(virsh -q domblklist ${VM} | awk '{print $1}'); do
        run qemu-img convert -f raw nbd+unix:///${disk}?socket=${TMPDIR}/sock -O raw $QEMU_FILE.${disk}
        echo "output = ${output}"
        [ "$status" -eq 0 ]
    done
}
@test "Stop backup job and nbd endpoint" {
    run ../virtnbdbackup -t raw -d $VM -k -o $BACKUPSET
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Extent: Query extents using qemu tools" {
    rm -rf ${TMPDIR}/extentquery
    run ../virtnbdbackup -q -l copy -d $VM -o ${TMPDIR}/extentquery -p
    echo "output = ${output}"
    [[ "$output" =~ "$EXTENT_OUTPUT1" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT2" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT3" ]]
}
@test "Extent: Query extents using extent handler" {
    rm -rf ${TMPDIR}/extentquery
    run ../virtnbdbackup -l copy -d $VM -o ${TMPDIR}/extentquery -p
    echo "output = ${output}"
    [[ "$output" =~ "$EXTENT_OUTPUT1" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT2" ]]
    [[ "$output" =~ "$EXTENT_OUTPUT3" ]]
}
@test "Backup raw using virtnbdbackup, query extents with extenthandler" {
    rm -rf $BACKUPSET
    if [ ! -z $HAS_RAW ]; then
        OPT="--raw"
    fi
    run ../virtnbdbackup -l copy $OPT -t raw -d $VM -o $BACKUPSET
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    [[ "$output" =~ "Creating full provisioned" ]]
}
@test "Compare backup image contents against reference image" {
    for disk in $(virsh -q domblklist ${VM} | awk '{print $1}'); do
        echo "Disk:${disk}" >&3
        run cmp -b $QEMU_FILE.${disk} "${BACKUPSET}/${disk}.copy.data"
        echo "output = ${output}"
        [ "$status" -eq 0 ]
    done
}
@test "Backup raw using virtnbdbackup, query extents with qemu-img" {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l copy -q -t raw -d $VM -o $BACKUPSET
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Compare backup image, extents queried via qemu tools" {
    if [ -z $HAS_RAW ]; then
        for disk in $(virsh -q domblklist ${VM} | awk '{print $1}'); do
            run cmp -b $QEMU_FILE.${disk} "${BACKUPSET}/${disk}.copy.data"
            echo "output = ${output}"
            [ "$status" -eq 0 ]
        done
    else
        run cmp -b $QEMU_FILE.sda "${BACKUPSET}/sda.copy.data"
        echo "output = ${output}"
        [ "$status" -eq 0 ]
    fi
}
@test "Backup in stream format"  {
    rm -rf $BACKUPSET
    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Backup in stream format, check if multiple writers are used"  {
    if [ ! -z $HAS_RAW ]; then
        OPT="--raw"
        echo "Raw disk attached Additional options: $OPT" >&3
    fi

    DISK_COUNT=$(virsh -q domblklist ${VM} | awk '{print $1}' | wc -l)
    if [ $DISK_COUNT == 2 ]; then
        rm -rf $BACKUPSET
        run ../virtnbdbackup -l copy -d $VM $OPT -o $BACKUPSET
        [ "$status" -eq 0 ]
        [[ "$output" =~ "Concurrent backup processes: [2]" ]]

        if [ ! -z $HAS_RAW ]; then
            [[ "$output" =~ "Creating full provisioned raw back" ]]
        fi
    else
        skip "vm has only one disk"
    fi
}
@test "Backup in stream format, limit writer to 1"  {
    if [ ! -z $HAS_RAW ]; then
        OPT="--raw"
        echo "Raw disk attached Additional options: $OPT" >&3
    fi

    DISK_COUNT=$(virsh -q domblklist ${VM} | awk '{print $1}' | wc -l)
    if [ $DISK_COUNT == 2 ]; then
        rm -rf $BACKUPSET
        run ../virtnbdbackup -l copy $OPT -d $VM -w 1 -o $BACKUPSET
        [ "$status" -eq 0 ]
        [[ "$output" =~ "Concurrent backup processes: [1]" ]]
    else
        skip "vm has only one disk"
    fi
}
toOut() {
    # for some reason bats likes to hijack stdout which results
    # in data being read into memory  ... helper function works
    # around this issue.
    ../virtnbdbackup -l full -d $VM -i sda -o - > ${TMPDIR}/backup.zip
}
@test "Full Backup in stream format, single disk write to stdout, check zip contents"  {
    rm -f ${TMPDIR}/backup.zip
    export PYTHONUNBUFFERED=True
    run toOut
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    [ -e ${TMPDIR}/backup.zip ]
    unzip -l ${TMPDIR}/backup.zip | grep sda.full.data
    [ "$status" -eq 0 ]
    unzip -l ${TMPDIR}/backup.zip | grep vmconfig.virtnbdbackup
    [ "$status" -eq 0 ]
    unzip -l ${TMPDIR}/backup.zip | grep backup.full..*.log
    [ "$status" -eq 0 ]
    unzip -l ${TMPDIR}/backup.zip | grep "${VM}.cpt"
    [ "$status" -eq 0 ]
    unzip -l ${TMPDIR}/backup.zip | grep checkpoints
    [ "$status" -eq 0 ]
    echo "output = ${output}"
}
@test "Dump metadata information" {
    run ../virtnbdrestore -i $BACKUPSET -a dump -o /dev/null
    echo "output = ${output}"
    [[ "$output" =~ "$DATA_SIZE" ]]
    [[ "$output" =~ "$VIRTUAL_SIZE" ]]
}
@test "Restore stream format"  {
    if [ ! -z $HAS_RAW ]; then
        OPT="--raw"
        echo "Raw disk attached Additional restore options: $OPT" >&3
    fi
    run ../virtnbdrestore -a restore $OPT -i $BACKUPSET -o $RESTORESET
    echo "output = ${output}"
    [[ "$output" =~ "End of stream" ]]
    [ "$status" -eq 0 ]
}
@test "Convert restored qcow2 image to RAW image, compare with reference image"  {
    if [ -z $HAS_RAW ]; then
        for disk in $(virsh -q domblklist ${VM} | awk '{print $1}'); do
            FILENAME="${VM}-${disk}.qcow2"
            echo $FILENAME >&3
            run qemu-img convert -f qcow2 -O raw $RESTORESET/${FILENAME} $RESTORESET/${disk}.raw
            echo "output = ${output}"
            [ "$status" -eq 0 ]
            run cmp $QEMU_FILE.${disk} $RESTORESET/${disk}.raw
            echo "output = ${output}"
            [ "$status" -eq 0 ]
        done
    else
        # restore includes raw files, must not be converted
        FILENAME="${VM}-sda.qcow2"
        echo $FILENAME >&3
        run qemu-img convert -f qcow2 -O raw $RESTORESET/${FILENAME} $RESTORESET/sda.raw
        echo "output = ${output}"
        [ "$status" -eq 0 ]
        run cmp $QEMU_FILE.sda $RESTORESET/sda.raw
        echo "output = ${output}"
        [ "$status" -eq 0 ]
        run cmp $QEMU_FILE.sdb $RESTORESET/${VM}-sdb.qcow2
        [ "$status" -eq 0 ]
    fi
}

# compression
@test "Backup in stream format: with and without compression, restore both and compare results"  {
    BACKUPSET_COMPRESSED="${TMPDIR}/testset_compressed"

    RESTOREDIR="${TMPDIR}/restore_uncompressed"
    RESTOREDIR_COMPRESSED="${TMPDIR}/restore_compressed"

    rm -rf $BACKUPSET $BACKUPSET_COMPRESSED

    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET
    echo "output = ${output}"
    [ "$status" -eq 0 ]

    run ../virtnbdbackup -l copy -d $VM -o $BACKUPSET_COMPRESSED --compress
    echo "output = ${output}"
    [ "$status" -eq 0 ]

    run ../virtnbdrestore -a restore -i $BACKUPSET_COMPRESSED -o $RESTOREDIR -n -v
    echo "output = ${output}"
    [ "$status" -eq 0 ]

    run ../virtnbdrestore -a restore -i $BACKUPSET_COMPRESSED -o $RESTOREDIR_COMPRESSED -n -v
    echo "output = ${output}"
    [ "$status" -eq 0 ]

    FILENAME=$(basename ${VM_IMAGE})

    run cmp ${TMPDIR}/restore_uncompressed/${FILENAME} ${TMPDIR}/restore_compressed/${FILENAME}
    echo "output = ${output}"
    [ "$status" -eq 0 ]

    rm -rf $RESTOREDIR $RESTOREDIR_COMPRESSED
}

# test for incremental backup

@test "Setup: Prepare test for incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    command -v guestmount || exit 1
    rm -rf ${TMPDIR}/inctest
}
@test "Backup: create full backup" {
    [ -z $INCTEST ] && skip "skipping"
    run ../virtnbdbackup -d $VM -l full -o ${TMPDIR}/inctest
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Setup: destroy VM" {
    [ -z $INCTEST ] && skip "skipping"
    run virsh destroy $VM
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Setup: mount disk via guestmount and create file" {
    [ -z $INCTEST ] && skip "skipping"
    mkdir -p /empty
    run guestmount -d $VM -m /dev/sda1  /empty/
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    echo incfile > /empty/incfile
    run umount /empty/
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Setup: start VM after creating file" {
    [ -z $INCTEST ] && skip "skipping"
    sleep 5 # not sure why..
    run virsh start $VM
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Backup: create first incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/inctest
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Backup: create second incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/inctest
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Restore: restore data and check if file from incremental backup exists" {
    [ -z $INCTEST ] && skip "skipping"
    rm -rf ${TMPDIR}/RESTOREINC/
    run ../virtnbdrestore -a restore -i ${TMPDIR}/inctest/ -o ${TMPDIR}/RESTOREINC/
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    FILENAME=$(basename ${VM_IMAGE})
    run guestmount -a ${TMPDIR}/RESTOREINC/${FILENAME} -m /dev/sda1  /empty
    [ "$status" -eq 0 ]
    echo "output = ${output}"
    [ -e /empty/incfile ]
    run umount /empty
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Restore: restore data until first incremental backup" {
    [ -z $INCTEST ] && skip "skipping"
    rm -rf ${TMPDIR}/RESTOREINC/
    run ../virtnbdrestore -a restore -i ${TMPDIR}/inctest/ --until virtnbdbackup.1 -o ${TMPDIR}/RESTOREINC/
    [[ "${output}" =~  "Reached checkpoint virtnbdbackup.1" ]]
    echo "output = ${output}"
}
