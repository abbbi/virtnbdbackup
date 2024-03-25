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
from argparse import Namespace
from libvirtnbdbackup.virt.client import DomainDisk

log = logging.getLogger("nbdctx")


def get(args: Namespace, disk: DomainDisk) -> str:
    """Get required meta context string passed to nbd server based on
    backup type"""
    metaContext = ""
    if args.level not in ("inc", "diff"):
        return metaContext

    if args.offline is True:
        metaContext = f"qemu:dirty-bitmap:{args.cpt.name}"
    else:
        metaContext = f"qemu:dirty-bitmap:backup-{disk.target}"

    logging.debug("Using NBD meta context [%s]", metaContext)

    return metaContext
