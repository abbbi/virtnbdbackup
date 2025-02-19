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
	TIMEOUT=120
	INTERVAL=5
	START_TIME=$(date +%s)
	while true; do
	    OUTPUT=$(virsh guestinfo fstrim 2>/dev/null || true)
	    if echo "$OUTPUT" | grep -q "arch"; then
		echo "Match found: 'arch' detected in output." >&3
		break
	    fi
	    CURRENT_TIME=$(date +%s)
	    ELAPSED_TIME=$((CURRENT_TIME - START_TIME))
	    if [ "$ELAPSED_TIME" -ge "$TIMEOUT" ]; then
		echo "Timeout reached: 2 minutes." >&3
		exit 1
	    fi
	    sleep "$INTERVAL"
	done
}
@test "Backup: create full backup" {
    run ../virtnbdbackup -d $VM -l full -o ${TMPDIR}/fstrim
    echo "output = ${output}"
    [[ "${output}" =~  "Saved qcow image config" ]]
    [ "$status" -eq 0 ]
}
@test "Execute fstrim" {
    run virsh domfstrim ${VM}
    echo "output = ${output}"
    [ "$status" -eq 0 ]
}
@test "Backup: create inc backup" {
    run ../virtnbdbackup -d $VM -l inc -o ${TMPDIR}/fstrim
    echo "output = ${output}"
    [[ "${output}" =~  "sparse bytes for current bitmap" ]]
    [ "$status" -eq 0 ]
}
@test "Restore: restore" {
    run ../virtnbdrestore -i ${TMPDIR}/fstrim -o ${TMPDIR}/restore
    [ "$status" -eq 0 ]
}
@test "Verify image contents" {
    run virt-ls -a ${TMPDIR}/restore/fstrim.qcow2 /
    [[ "${output}" =~  "boot" ]]
    [ "$status" -eq 0 ]
}
