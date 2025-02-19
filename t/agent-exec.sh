#!/bin/bash
# helper script to execute commands within test VM
# using qemu guest agent

execute_qemu_command() {
    vm_name="$1"
    command="$2"
    shift 2
    params="$@"

    if [ -n "$params" ]; then
        json_payload="{\"execute\": \"guest-exec\", \"arguments\": {\"path\": \"$command\", \"arg\": $params, \"capture-output\": true}}"
    else
        json_payload="{\"execute\": \"guest-exec\", \"arguments\": {\"path\": \"$command\", \"capture-output\": true}}"
    fi

    # Execute the command using virsh
    exec_result=$(virsh qemu-agent-command "$vm_name" "$json_payload" --timeout 5 2>&1)
    exit_code=$?

    if [ $exit_code -ne 0 ]; then
        echo "Error executing QEMU agent command: $exec_result" >&3
        return $exit_code
    fi
    pid=$(echo "$exec_result" | jq -r '.return.pid //empty')
    if [ -z "$pid" ]; then
        echo "Failed to retrieve PID from guest-exec response." >&3
        return 1
    fi
    status_payload="{\"execute\": \"guest-exec-status\", \"arguments\": {\"pid\": $pid}}"
    while true; do
        status_result=$(virsh qemu-agent-command "$vm_name" "$status_payload" --timeout 5 2>&1)
        if [ $? -ne 0 ]; then
            echo "Error fetching guest-exec-status: $status_result" >&3
            return 1
        fi
        exited=$(echo "$status_result" | jq -r '.return.exited')
        if [ "$exited" = "true" ]; then
            exit_code=$(echo "$status_result" | jq -r '.return.exitcode')
            out_data=$(echo "$status_result" | jq -r '.return."out-data" //empty' | base64 -d)
            err_data=$(echo "$status_result" | jq -r '.return."err-data" //empty' | base64 -d)
            break
        fi
        sleep 1
    done

    if [ -n "$err_data" ]; then
        echo "Error output: $err_data" >&3
    fi

    if [ -n "$out_data" ]; then
        echo "Output: $out_data"
    fi

    return "$exit_code"
}

#execute_qemu_command fstrim "mkdir" '["/incdata"]'
#execute_qemu_command fstrim "/bin/ls" '["/"]'
