if [ -z "$TEST" ]; then
    echo ""
    echo "Missing required test env" >&2
    echo "export TEST=<dir> to run specified tests" >&2
    echo ""
    exit
fi

if [ -e /root/agent ]; then
    source /root/agent > /dev/null
fi

if [ -z "$TMPDIR" ]; then
    export TMPDIR=$(mktemp -d)
    chmod go+rwx $TMPDIR
fi

load $TEST/config.bash


setup() {
 aa-teardown >/dev/null || true
}

@test "Setup / download vm image ${IMG_URL} to ${TMPDIR}/${VM_IMAGE}" {
    rm -f  ${TMPDIR}/${VM_IMAGE} 10M
    qemu-img create -f qcow2 ${TMPDIR}/${VM_IMAGE} 10M
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
@test "Backup: create full backup" {
    run ../virtnbdbackup -d $VM -l full -o ${TMPDIR}/fstrim
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Destroy VM" {
    run virsh destroy $VM
    [ "$status" -eq 0 ]
}
@test "Change one 64k block with data" {
    run qemu-io -c "write 1M 64k" ${TMPDIR}/${VM_IMAGE}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Start VM" {
    run virsh start $VM
    [ "$status" -eq 0 ]
}
@test "Backup: create incremental backup: one data block must be detected" {
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/fstrim
    echo "output = ${output}"
    [[ "${output}" =~  "65536 bytes [64.0KiB] of data extents to backup" ]]
    [ "$status" -eq 0 ]
}
@test "Destroy VM 1" {
    run virsh destroy $VM
    [ "$status" -eq 0 ]
}
@test "Change one 64k block with data one 64k block with zeroes" {
    run qemu-io -c "write 1M 64k" ${TMPDIR}/${VM_IMAGE}
    run qemu-io -c "write -z 2M 64k" ${TMPDIR}/${VM_IMAGE}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Start VM 1" {
    run virsh start $VM
    [ "$status" -eq 0 ]
}
@test "Backup: create incremental backup: one data, one sparse block must be detected" {
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/fstrim
    echo "output = ${output}"
    [[ "${output}" =~  "Detected 65536 bytes [64.0KiB] sparse blocks for current bitmap" ]]
    [[ "${output}" =~  "65536 bytes [64.0KiB] of data extents to backup" ]]
    [ "$status" -eq 0 ]
}

