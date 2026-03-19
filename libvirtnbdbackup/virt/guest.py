"""
Copyright (C) 2026  Michael Ablassmeier <abi@grinser.de>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import json
import time
import base64
from typing import Tuple, Any
import libvirt
import libvirt_qemu


def Exec(
    domObj: libvirt.virDomain,
    command: str,
    args: str,
    timeout: int = 30,
) -> Tuple[Any, Any]:
    """Execute command within VM using guest-agent"""

    def agent_cmd(payload: dict) -> dict:
        body = json.dumps(payload)
        # Some bindings expose this on virDomain, others via libvirt_qemu.
        if hasattr(domObj, "qemuAgentCommand"):
            raw = domObj.qemuAgentCommand(body, timeout, 0)
        else:
            raw = libvirt_qemu.qemuAgentCommand(domObj, body, timeout, 0)
        return json.loads(raw)

    # Start process in guest.
    payload = {
        "execute": "guest-exec",
        "arguments": {
            "path": f"{command}",
            "arg": [f"{args}"],
            "capture-output": True,
        },
    }
    result = agent_cmd(payload)
    pid = result["return"]["pid"]

    # Poll for completion.
    deadline = time.time() + timeout
    while time.time() < deadline:
        status_req = {
            "execute": "guest-exec-status",
            "arguments": {"pid": pid},
        }
        status = agent_cmd(status_req)["return"]
        if status.get("exited"):
            # TODO: handle error, raise
            # status.get("exitcode", 1))
            out_data = status.get("out-data")
            err_data = status.get("err-data")
            return base64.b64decode(out_data).decode(
                errors="replace"
            ), base64.b64decode(err_data).decode(errors="replace")
        time.sleep(0.5)

    raise TimeoutError(f"Timed out waiting for command in guest (pid={pid})")
