"""
Copyright (C) 2023  Michael Ablassmeier <abi@grinser.de>

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

import logging
import socket
from typing import Tuple, Callable, Optional
from enum import Enum
from paramiko import (
    AutoAddPolicy,
    SSHClient,
    SFTPClient,
    SSHException,
    AuthenticationException,
)
from libvirtnbdbackup.ssh import exceptions
from libvirtnbdbackup.objects import processInfo

log = logging.getLogger("ssh")


class Mode(Enum):
    """Up or download mode"""

    UPLOAD = 1
    DOWNLOAD = 2


class client:
    """Wrapper around paramiko/sftp put and get functions, to be able to
    remote copy files from hypervisor host"""

    def __init__(
        self, host: str, user: str, port: int = 22, mode: Mode = Mode.DOWNLOAD
    ):
        self.client = None
        self.host = host
        self.user = user
        self.port = port
        self.copy: Callable[[str, str], None] = self.copyFrom
        if mode == Mode.UPLOAD:
            self.copy = self.copyTo
        self.connection = self.connect()
        self._sftp: Optional[SFTPClient] = None

    def connect(self) -> SSHClient:
        """Connect to remote system"""
        log.info(
            "Connecting remote system [%s] via ssh, username: [%s]",
            self.host,
            self.user,
        )
        try:
            cli = SSHClient()
            cli.load_system_host_keys()
            cli.set_missing_host_key_policy(AutoAddPolicy())
            cli.connect(
                self.host,
                username=self.user,
                port=self.port,
                timeout=5000,
            )
            return cli
        except AuthenticationException as e:
            raise exceptions.sshError(f"SSH key authentication failed: {e}")
        except socket.gaierror as e:
            raise exceptions.sshError(f"Unable to connect: {e}")
        except SSHException as e:
            raise exceptions.sshError(e)
        except Exception as e:
            log.exception(e)
            raise exceptions.sshError(f"Unhandled exception occurred: {e}")

    @property
    def sftp(self) -> SFTPClient:
        """Return SFTP client, opening connection on first use."""
        if self._sftp is None:
            self._sftp = self.connection.open_sftp()
        return self._sftp

    def exists(self, filepath: str) -> bool:
        """
        Check if remote file exists
        """
        try:
            self.sftp.stat(filepath)
            return True
        except IOError:
            return False

    def copyFrom(self, filepath: str, localpath: str) -> None:
        """
        Get file from remote system
        """
        log.info("Downloading file [%s] to [%s]", filepath, localpath)
        try:
            self.sftp.get(filepath, localpath)
        except SSHException as e:
            log.warning("Unable to download file: [%s]", e)

    def copyTo(self, localpath: str, remotepath: str) -> None:
        """
        Put file to remote system
        """
        log.info("Uploading file [%s] to [%s]", localpath, remotepath)
        try:
            self.sftp.put(localpath, remotepath)
        except SSHException as e:
            log.warning("Unable to upload file: [%s]", e)

    def _execute(self, cmd) -> Tuple[int, str, str]:
        _, stdout, stderr = self.connection.exec_command(cmd)
        ret = stdout.channel.recv_exit_status()
        err = stderr.read().strip().decode()
        out = stdout.read().strip().decode()
        return ret, err, out

    def run(self, cmd: str, pidFile: str = "", logFile: str = "") -> processInfo:
        """
        Execute command
        """
        pid: int = 0
        pidOut: str
        log.debug("Executing remote command: [%s]", cmd)
        ret, err, out = self._execute(cmd)
        logerr = ""
        if ret == 127:
            raise exceptions.sshError(err)
        if ret != 0:
            log.error(
                "Executing remote command failed, return code: [%s] stderr: [%s], stdout: [%s]",
                ret,
                err,
                out,
            )
            if logFile:
                log.debug("Attempting to catch errors from logfile: [%s]", logFile)
                _, _, logerr = self._execute(f"cat {logFile}")
            raise exceptions.sshError(
                f"Error during remote command: [{cmd}]: [{err}] [{logerr}]"
            )

        if pidFile:
            log.debug("PIDfile: [%s]", pidFile)
            _, _, pidOut = self._execute(f"cat {pidFile}")
            pid = int(pidOut)
            log.debug("PID: [%s]", pid)

        return processInfo(pid, logFile, err, out, pidFile)

    def disconnect(self):
        """Disconnect"""
        if self._sftp is not None:
            self._sftp.close()
            self._sftp = None
        if self.connection:
            self.connection.close()
