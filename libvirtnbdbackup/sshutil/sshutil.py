"""
    Copyright (C) 2022  Michael Ablassmeier <abi@grinser.de>

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
from paramiko import AutoAddPolicy, SSHClient
from paramiko.auth_handler import AuthenticationException
from scp import SCPClient, SCPException

from libvirtnbdbackup.sshutil import exceptions
from libvirtnbdbackup.common.common import processInfo

log = logging.getLogger(__name__)


class Client:
    """Wrapper around paramiko/scp put and get functions, to be able to
    remote copy files from hypervisor host"""

    def __init__(self, host: str, user: str):
        self.client = None
        self.host = host
        self.user = user
        self.connection = self.connect()

    def connect(self):
        """Connect to remote system"""
        log.info("Connecting remote system via ssh, username: [%s]", self.user)
        try:
            client = SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(AutoAddPolicy())
            client.connect(
                self.host,
                username=self.user,
                timeout=5000,
            )
            return client
        except AuthenticationException as e:
            raise exceptions.sshutilError(
                f"AuthenticationException occurred; did you remember to generate an SSH key? {e}"
            )
        except Exception as e:
            raise exceptions.sshutilError(f"Unknown exception occured: {e}")

    @property
    def scp(self) -> SCPClient:
        """Copy file"""
        return SCPClient(self.connection.get_transport())

    def copyFrom(self, filepath: str, localpath: str):
        """
        Get file from remote system
        """
        log.info("Downloading file [%s] to [%s]", filepath, localpath)
        try:
            self.scp.get(filepath, localpath)
        except SCPException as e:
            logging.warning("Error during file copy: [%s]", e)

    def copyTo(self, localpath: str, remotepath: str):
        """
        Put file to remote system
        """
        log.info("Uploading file [%s] to [%s]", localpath, remotepath)
        try:
            self.scp.put(localpath, remotepath)
        except SCPException as e:
            logging.warning("Error during file copy: [%s]", e)

    def _execute(self, cmd):
        _, stdout, stderr = self.connection.exec_command(cmd)
        ret = stdout.channel.recv_exit_status()
        err = stderr.read().strip().decode()
        out = stdout.read().strip().decode()
        return ret, err, out

    def run(self, cmd: str, pidFile: str = None, logFile: str = None):
        """
        Execute command
        """
        pid = None
        logging.debug("Executing command: [%s]", cmd)
        ret, err, out = self._execute(cmd)
        if ret != 0:
            if logFile:
                _, _, err = self._execute(f"cat {logFile}")
            raise exceptions.sshutilError(
                f"Error during remote command: [{cmd}]: [{err}]"
            )

        if pidFile:
            logging.debug("PIDfile: [%s]", pidFile)
            _, _, pid = self._execute(f"cat {pidFile}")
            logging.debug("PID: [%s]", pid)

        return processInfo(pid, logFile, err, out)

    def disconnect(self):
        """Disconnect"""
        if self.scp:
            self.scp.close()
        if self.connection:
            self.connection.close()
