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
import os
import logging
from time import sleep
import nbd
from libvirtnbdbackup.nbdcli import exceptions

log = logging.getLogger("nbd")


class client:
    """Helper functions for NBD"""

    def __init__(self, cType):
        """
        Connect NBD backend
        """
        self.cType = cType
        self._exportName = cType.exportName
        if cType.metaContext == "":
            self._metaContext = nbd.CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = cType.metaContext
        self.maxRequestSize = 33554432
        self.minRequestSize = 65536
        self.nbd = nbd.NBD()

        def debug(func, args):
            """Write NBD debugging messages to logfile instead of
            stderr"""
            log.debug("%s: %s", func, args)

        self.nbd.set_debug_callback(debug)
        self.connection = None

    def _getBlockInfo(self) -> None:
        """Read maximum request/block size as advertised by the nbd
        server. This is the value which will then be used by default
        """
        maxSize = self.nbd.get_block_size(nbd.SIZE_MAXIMUM)
        if maxSize != 0:
            self.maxRequestSize = maxSize

        log.debug("Block size supported by NBD server: [%s]", maxSize)

    def _connect(self) -> nbd.NBD:
        """Setup connection to NBD server endpoint, return
        connection handle
        """
        if self.cType.tls and not self.nbd.supports_tls():
            raise exceptions.NbdConnectionError(
                "Installed python nbd binding is missing required tls features."
            )

        try:
            if self.cType.tls:
                self.nbd.set_tls(nbd.TLS_REQUIRE)
            self.nbd.add_meta_context(self._metaContext)
            self.nbd.set_export_name(self._exportName)
            self.nbd.connect_uri(self.cType.uri)
        except nbd.Error as e:
            raise exceptions.NbdConnectionError(f"Unable to connect nbd server: {e}")

        self._getBlockInfo()

        return self.nbd

    def connect(self) -> nbd.NBD:
        """Wait until NBD endpoint connection can be established. It can take
        some time until qemu-nbd process is running and reachable. Attempt to
        connect and fail if no connection can be established. In case of unix
        domain socket, wait until socket file is created by qemu-nbd."""
        log.info("Waiting until NBD server at [%s] is up.", self.cType.uri)
        retry = 0
        maxRetry = 20
        sleepTime = 1
        while True:
            sleep(sleepTime)
            if retry >= maxRetry:
                raise exceptions.NbdConnectionTimeout(
                    "Timeout during connection to NBD server backend."
                )

            if self.cType.backupSocket and not os.path.exists(self.cType.backupSocket):
                log.info("Waiting for NBD Server unix socket, Retry: %s", retry)
                retry = retry + 1
                continue

            try:
                connection = self._connect()
            except exceptions.NbdConnectionError as e:
                self.nbd = nbd.NBD()
                log.info("Waiting for NBD Server connection, Retry: %s [%s]", retry, e)
                retry = retry + 1
                continue

            log.info("Connection to NBD backend succeeded.")
            self.connection = connection
            return self

    def disconnect(self) -> None:
        """Close nbd connection handle"""
        self.nbd.shutdown()
