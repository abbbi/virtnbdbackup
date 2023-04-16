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
from lxml.etree import _Element
from lxml import etree as ElementTree

log = logging.getLogger()


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
