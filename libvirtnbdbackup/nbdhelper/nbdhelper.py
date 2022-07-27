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
from dataclasses import dataclass
import nbd
from libvirtnbdbackup.nbdhelper import exceptions

log = logging.getLogger(__name__)


@dataclass
class nbdConn:
    """NBD connection"""

    exportName: str
    metaContext: str


@dataclass
class nbdConnUnix(nbdConn):
    """NBD connection type unix"""

    backupSocket: str

    def __post_init__(self):
        self.uri = f"nbd+unix:///{self.exportName}?socket={self.backupSocket}"


@dataclass
class nbdConnTCP(nbdConn):
    """NBD connection type tcp"""

    hostname: str
    port: int = 10809
    backupSocket: str = None

    def __post_init__(self):
        self.uri = f"nbd://{self.hostname}:{self.port}/{self.exportName}"


class nbdClient:
    """Helper functions for NBD"""

    def __init__(self, cType):
        """
        Connect NBD backend, currently only unix type socket
        communication implemented. Should be extended to support
        TCP based remote backup too (#65)
        """
        self._uri = cType.uri
        self._exportName = cType.exportName
        self._socket = cType.backupSocket
        if cType.metaContext is None:
            self._metaContext = nbd.CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = cType.metaContext
        self.maxRequestSize = 33554432
        self.minRequestSize = 65536
        self.nbd = nbd.NBD()
        self.version()

    @staticmethod
    def version():
        """Log libnbd version"""
        log.info("libnbd version: %s", nbd.__version__)

    def getBlockInfo(self):
        """Read maximum request/block size as advertised by the nbd
        server. This is the value which will then be used by default
        """
        maxSize = self.nbd.get_block_size(nbd.SIZE_MAXIMUM)
        if maxSize != 0:
            self.maxRequestSize = maxSize

        log.info("Using Maximum Block size supported by NBD server: [%s]", maxSize)

    def connect(self):
        """Setup connection to NBD server endpoint, return
        connection handle
        """
        try:
            self.nbd.add_meta_context(self._metaContext)
            self.nbd.set_export_name(self._exportName)
            self.nbd.connect_uri(self._uri)
        except nbd.Error as e:
            raise exceptions.NbdConnectionError(f"Unable to connect nbd server: {e}")

        self.getBlockInfo()

        return self.nbd

    def waitForServer(self):
        """Wait until NBD endpoint connection can be established"""
        logging.info("Waiting until NBD server at [%s] is up.", self._uri)
        retry = 0
        maxRetry = 20
        sleepTime = 1
        while True:
            sleep(sleepTime)
            if retry >= maxRetry:
                raise exceptions.NbdConnectionTimeout(
                    "Timeout during connection to NBD server backend."
                )

            if self._socket and not os.path.exists(self._socket):
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
        self.nbd.shutdown()
