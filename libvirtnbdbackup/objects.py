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

import ipaddress
from dataclasses import dataclass


@dataclass
class processInfo:
    """Process info object returned by functions calling
    various qemu commands
    """

    pid: int
    logFile: str
    err: str
    out: str
    pidFile: str


@dataclass
class DomainDisk:
    """Domain disk object holding information about the disk
    attached to a virtual machine"""

    target: str
    format: str
    filename: str
    path: str
    backingstores: list
    discardOption: str


@dataclass
class nbdConn:
    """NBD connection"""

    exportName: str
    metaContext: str


@dataclass
class Unix(nbdConn):
    """NBD connection type unix for connection via socket file"""

    backupSocket: str
    tls: bool = False

    def __post_init__(self):
        self.uri = f"nbd+unix:///{self.exportName}?socket={self.backupSocket}"


@dataclass
class TCP(nbdConn):
    """NBD connection type tcp for remote backup"""

    hostname: str
    tls: bool
    port: int = 10809
    backupSocket: str = ""
    uri_prefix = "nbd://"

    def __post_init__(self):
        if self.tls:
            self.uri_prefix = "nbds://"

        try:
            ip = ipaddress.ip_address(self.hostname)
            if ip.version == 6:
                self.hostname = f"[{self.hostname}]"
        except ValueError:
            pass

        self.uri = f"{self.uri_prefix}{self.hostname}:{self.port}/{self.exportName}"


@dataclass
class Extent:
    """Extent description containing information if block contains
    data, offset and length of data to be read/written"""

    context: str
    data: bool
    offset: int
    length: int


@dataclass
class _ExtentObj:
    """Single Extent object as returned from the NBD server"""

    context: str
    length: int
    type: int
