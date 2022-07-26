#!/usr/bin/python3
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
from getpass import getuser
from libvirtnbdbackup import __version__


def addRemoteArgs(opt):
    """Common remote backup arguments"""
    opt.add_argument(
        "-U",
        "--uri",
        default="qemu:///system",
        required=False,
        type=str,
        help="Libvirt connection URI. (default: %(default)s)",
    )
    opt.add_argument(
        "--user",
        default=None,
        required=False,
        type=str,
        help="User to authenticate against libvirtd. (default: %(default)s)",
    )
    opt.add_argument(
        "--ssh-user",
        default=getuser() or None,
        required=False,
        type=str,
        help=(
            "User to authenticate against remote sshd: "
            "used for remote copy of files. (default: %(default)s)"
        ),
    )
    opt.add_argument(
        "--password",
        default=None,
        required=False,
        type=str,
        help="Password to authenticate against libvirtd. (default: %(default)s)",
    )
    opt.add_argument(
        "-P",
        "--nbd-port",
        type=int,
        default=10809,
        required=False,
        help=(
            "Port used by remote NDB Service, should be unique for each"
            " started backup. (default: %(default)s)"
        ),
    )
    opt.add_argument(
        "-I",
        "--nbd-ip",
        type=str,
        default=None,
        required=False,
        help=(
            "IP used to bind remote NBD service on"
            " (default: hostname returned by libvirtd)"
        ),
    )
    opt.add_argument(
        "-T",
        "--tls",
        action="store_true",
        required=False,
        help="Enable and use TLS for NBD connection. (default: %(default)s)",
    )


def addDebugArgs(opt):
    """Common debug arguments"""
    opt.add_argument(
        "-v",
        "--verbose",
        default=False,
        help="Enable debug output",
        action="store_true",
    )
    opt.add_argument(
        "-V",
        "--version",
        default=False,
        help="Show version and exit",
        action="version",
        version=__version__,
    )
