"""
    Copyright (C) 2021  Michael Ablassmeier <abi@grinser.de>

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
import os
import logging
from time import sleep
import nbd
from libvirtnbdbackup.nbdhelper import exceptions

log = logging.getLogger(__name__)


class nbdClient:
    """Helper functions for NBD"""

    def __init__(self, exportName, metaContext, backupSocket):
        """Parameters:
        :exportName: name of nbd export
        :backupSocket: ndb server endpoint
        """
        self._socket = backupSocket
        self._exportName = exportName
        if metaContext is None:
            self._metaContext = nbd.CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = metaContext

        self.maxRequestSize = 33554432
        self.minRequestSize = 65536

        self._connectionHandle = None

        self._nbdHandle = nbd.NBD()

        self.version()

    @staticmethod
    def version():
        """Log libnbd version"""
        log.info("libnbd version: %s", nbd.__version__)

    def getBlockInfo(self):
        """Read maximum request/block size as advertised by the nbd
        server. This is the value which will then be used by default
        """
        maxSize = self._nbdHandle.get_block_size(nbd.SIZE_MAXIMUM)
        if maxSize != 0:
            self.maxRequestSize = maxSize

        log.info("Using Maximum Block size supported by NBD server: [%s]", maxSize)

    def connect(self):
        """Setup connection to NBD server endpoint, return
        connection handle
        """
        try:
            self._nbdHandle.add_meta_context(self._metaContext)
            self._nbdHandle.set_export_name(self._exportName)
            self._nbdHandle.connect_unix(self._socket)
        except nbd.Error as e:
            raise exceptions.NbdConnectionError(f"Unable to connect nbd server: {e}")

        self.getBlockInfo()

        return self._nbdHandle

    def startRestoreNbdServer(self, targetFile):
        """Start nbd server process for restore operation using
        libnbd's builtin socket activation method'"""
        cmd = [
            "qemu-nbd",
            "--discard=unmap",
            "--format=qcow2",
            f"{targetFile}",
        ]
        self._nbdHandle.connect_systemd_socket_activation(cmd)
        return self._nbdHandle

    def waitForServer(self):
        """Wait until NBD endpoint connection can be established"""
        logging.info("Waiting until NBD server on socket [%s] is up.", self._socket)
        retry = 0
        maxRetry = 20
        sleepTime = 1
        while True:
            sleep(sleepTime)
            if retry >= maxRetry:
                raise exceptions.NbdConnectionTimeout(
                    "Timeout during connection to NBD server backend."
                )

            if not os.path.exists(self._socket):
                logging.info("Waiting for NBD Server, Retry: %s", retry)
                retry = retry + 1

            connection = self.connect()
            if connection:
                logging.info("Connection to NBD backend succeeded.")
                return connection

            logging.info("Waiting for NBD Server, Retry: %s", retry)
            retry = retry + 1

    def disconnect(self):
        """Close nbd connection handle"""
        self._nbdHandle.shutdown()
