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
load agent-exec.sh


setup() {
 aa-teardown >/dev/null || true
}

@test "Setup / download vm image ${IMG_URL} to ${TMPDIR}/${VM_IMAGE}" {
    if [ ! -e ${TMPDIR}/${VM_IMAGE} ]; then
        curl -Ls ${IMG_URL} -o ${TMPDIR}/${VM_IMAGE}
    fi
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
@test "Wait for VM to be reachable via guest agent" {
    run wait_for_agent $VM
}
@test "Backup: create full backup" {
    run ../virtnbdbackup -d $VM -l full -o ${TMPDIR}/cbtmiss
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Create data in VM 1" {
    run execute_qemu_command $VM "cp" '["-a", "/etc", "/incdata"]'
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    run execute_qemu_command $VM sync
    [ "$status" -eq 0 ]
}
@test "Stop VM and remove CBT" {
    run virsh destroy ${VM}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    run qemu-img info ${TMPDIR}/cbtmiss.qcow2
    echo "output = ${output}"
    run qemu-img bitmap ${TMPDIR}/cbtmiss.qcow2 --remove virtnbdbackup.0
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Start VM again" {
    run virsh start ${VM}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    echo "output = ${output}"
    run wait_for_agent $VM
}
@test "Backup: create incremental backup" {
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/cbtmiss
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Create data in VM 2" {
    run execute_qemu_command $VM "cp" '["-a", "/etc", "/incdata2"]'
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    run execute_qemu_command $VM sync
    [ "$status" -eq 0 ]
}
@test "Backup: create one more incremental backup" {
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/cbtmiss
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Create data in VM 3" {
    run execute_qemu_command $VM "cp" '["-a", "/etc", "/incdata3"]'
    [ "$status" -eq 0 ]
    run execute_qemu_command $VM sync
    [ "$status" -eq 0 ]
}
@test "Stop VM and remove CBT 2" {
    run virsh destroy ${VM}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
    run qemu-img info ${TMPDIR}/cbtmiss.qcow2
    echo "output = ${output}"
    run qemu-img bitmap ${TMPDIR}/cbtmiss.qcow2 --remove virtnbdbackup.2
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Backup: create inc backup on offline VM" {
    run ../virtnbdbackup -d $VM -l inc -S -o ${TMPDIR}/cbtmiss
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Restore: restore vm with new name" {
    run ../virtnbdrestore -cD --name restored -i ${TMPDIR}/cbtmiss -o ${TMPDIR}/restore
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Verify image contents" {
    run virt-ls -a ${TMPDIR}/restore/cbtmiss.qcow2 /
    [[ "${output}" =~  "incdata" ]]
    [ "$status" -eq 0 ]

    run virt-ls -a ${TMPDIR}/restore/cbtmiss.qcow2 /incdata
    [[ "${output}" =~  "sudoers" ]]
    [ "$status" -eq 0 ]

    run virt-cat -a ${TMPDIR}/restore/cbtmiss.qcow2 /incdata/sudoers
    [[ "${output}" =~  "Uncomment" ]]
    [ "$status" -eq 0 ]

    run virt-ls -a ${TMPDIR}/restore/cbtmiss.qcow2 /incdata2
    [[ "${output}" =~  "sudoers" ]]
    [ "$status" -eq 0 ]

    run virt-ls -a ${TMPDIR}/restore/cbtmiss.qcow2 /incdata3
    [[ "${output}" =~  "sudoers" ]]
    [ "$status" -eq 0 ]
}
@test "Start restored VM" {
    run virsh start restored
    [ "$status" -eq 0 ]
}
@test "Verify restored VM boots" {
    run wait_for_agent restored
    [ "$status" -eq 0 ]
}
@test "Check filesystem consistency after boot" {
    run execute_qemu_command restored btrfs '["device","stats","-c", "/"]'
    [ "$status" -eq 0 ]
    echo "output = ${output}"
}
