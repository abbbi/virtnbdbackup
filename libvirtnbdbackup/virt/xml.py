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
from typing import List, Optional, Tuple, Dict

from lxml.etree import _Element
from lxml import etree as ElementTree

log = logging.getLogger()


# -----------------------------
# Existing helpers
# -----------------------------
def asTree(vmConfig: str) -> _Element:
    """Return Etree element for vm config"""
    return ElementTree.fromstring(vmConfig)


def indent(top: _Element) -> str:
    """Indent xml output for debug log"""
    try:
        ElementTree.indent(top)
    except ElementTree.ParseError as errmsg:
        log.debug("Failed to parse xml: [%s]", errmsg)
    except AttributeError:
        # older ElementTree versions dont have the
        # indent method, skip silently and use
        # non formatted string
        pass

    xml = ElementTree.tostring(top).decode()
    log.debug("\n%s", xml)

    return xml


# -----------------------------
# New RBD-aware helpers
# -----------------------------
def disks(tree: _Element) -> List[_Element]:
    """Return a list of <disk> elements from a libvirt domain XML tree."""
    return list(tree.xpath("devices/disk"))


def disk_type(disk: _Element) -> Optional[str]:
    """Return the disk 'type' attribute (file|block|network|volume|...)"""
    return disk.get("type")


def disk_device(disk: _Element) -> Optional[str]:
    """Return the disk 'device' attribute (disk|cdrom|floppy|lun)"""
    return disk.get("device")


def disk_target_dev(disk: _Element) -> Optional[str]:
    """Return the disk target dev (e.g. vda)"""
    tgt = disk.find("target")
    return tgt.get("dev") if tgt is not None else None


def disk_driver_type(disk: _Element) -> Optional[str]:
    """Return the disk driver/@type (e.g. qcow2|raw)"""
    drv = disk.find("driver")
    return drv.get("type") if drv is not None else None


def disk_source(disk: _Element) -> Optional[_Element]:
    """Return the <source> element of a disk."""
    return disk.find("source")


def is_rbd_disk(disk: _Element) -> bool:
    """
    Return True if disk is <disk type='network'> with <source protocol='rbd'>.
    """
    if disk_type(disk) != "network":
        return False
    src = disk_source(disk)
    if src is None:
        return False
    return src.get("protocol") == "rbd"


def rbd_name(disk: _Element) -> Optional[str]:
    """
    Return the Ceph RBD name attribute 'pool/image' from <source name='...'>, or None.
    """
    if not is_rbd_disk(disk):
        return None
    src = disk_source(disk)
    return src.get("name") if src is not None else None


def rbd_pool_image(disk: _Element) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (pool, image) tuple for an RBD disk, or (None, None).
    """
    name = rbd_name(disk)
    if not name or "/" not in name:
        return None, None
    pool, image = name.split("/", 1)
    return pool, image


def rbd_hosts(disk: _Element) -> List[Tuple[Optional[str], Optional[str]]]:
    """
    Return a list of (host, port) tuples defined for RBD <source>.
    """
    out: List[Tuple[Optional[str], Optional[str]]] = []
    if not is_rbd_disk(disk):
        return out
    src = disk_source(disk)
    if src is None:
        return out
    for h in src.findall("host"):
        out.append((h.get("name"), h.get("port")))
    return out


def rbd_auth(disk: _Element) -> Dict[str, Optional[str]]:
    """
    Return RBD auth details:
      {
        'username': <auth/@username or None>,
        'secret_uuid': <auth/secret/@uuid or None>
      }
    """
    res = {"username": None, "secret_uuid": None}
    if not is_rbd_disk(disk):
        return res
    auth = disk.find("auth")
    if auth is not None:
        res["username"] = auth.get("username")
        secret = auth.find("secret")
        if secret is not None:
            res["secret_uuid"] = secret.get("uuid")
    return res


def set_rbd_name(disk: _Element, pool: str, image: str) -> None:
    """
    Update <source name='pool/image'> for an RBD disk. Keeps <host> and <auth> intact.
    """
    if not is_rbd_disk(disk):
        log.debug("set_rbd_name: disk is not an RBD disk, skipping.")
        return
    src = disk_source(disk)
    if src is None:
        log.debug("set_rbd_name: no <source> element found, skipping.")
        return
    src.set("name", f"{pool}/{image}")


def ensure_rbd_source(
    disk: _Element,
    pool: str,
    image: str,
    hosts: Optional[List[Tuple[str, str]]] = None,
    username: Optional[str] = None,
    secret_uuid: Optional[str] = None,
) -> None:
    """
    Ensure a disk has an RBD <source>. This can be used when converting a file/block disk
    to an RBD-based disk in the XML.

    - Sets type='network' and <source protocol='rbd' name='pool/image'>.
    - Preserves existing <target>, <driver>, etc.
    - Optionally sets <host> elements and <auth/secret>.
    """
    # Mark disk as network/RBD
    disk.set("type", "network")
    src = disk_source(disk)
    if src is None:
        # Create source element in the expected position (order is not critical for libvirt)
        src = ElementTree.SubElement(disk, "source")

    src.attrib.clear()
    src.set("protocol", "rbd")
    src.set("name", f"{pool}/{image}")

    # Hosts
    # Remove any existing host children first
    for h in list(src.findall("host")):
        src.remove(h)
    if hosts:
        for host, port in hosts:
            host_el = ElementTree.SubElement(src, "host")
            if host:
                host_el.set("name", host)
            if port:
                host_el.set("port", port)

    # Auth
    auth_el = disk.find("auth")
    if username or secret_uuid:
        if auth_el is None:
            auth_el = ElementTree.SubElement(disk, "auth")
        auth_el.attrib.clear()
        if username:
            auth_el.set("username", username)
        # secret child
        secret_el = auth_el.find("secret")
        if secret_el is None:
            secret_el = ElementTree.SubElement(auth_el, "secret")
        secret_el.attrib.clear()
        if secret_uuid:
            secret_el.set("type", "ceph")
            secret_el.set("uuid", secret_uuid)
    elif auth_el is not None:
        # If no auth requested, ensure no stale auth remains (optional choice)
        pass

