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
import libvirt

log = logging.getLogger("fs")


def freeze(domObj: libvirt.virDomain, mountpoints: None) -> bool:
    """Attempt to freeze domain filesystems using qemu guest agent"""
    state, _ = domObj.state()
    if state == libvirt.VIR_DOMAIN_PAUSED:
        log.info("Skip freezing filesystems: domain is in paused state")
        return False

    log.debug("Attempting to freeze filesystems.")
    try:
        if mountpoints is not None:
            frozen = domObj.fsFreeze(mountpoints.split(","))
        else:
            frozen = domObj.fsFreeze()
        log.info("Freezed [%s] filesystems.", frozen)
        return True
    except libvirt.libvirtError as errmsg:
        log.warning(errmsg)
        return False


def thaw(domObj: libvirt.virDomain) -> bool:
    """Thaw freezed filesystems"""
    log.debug("Attempting to thaw filesystems.")
    try:
        thawed = domObj.fsThaw()
        log.info("Thawed [%s] filesystems.", thawed)
        return True
    except libvirt.libvirtError as errmsg:
        log.warning(errmsg)
        return False
