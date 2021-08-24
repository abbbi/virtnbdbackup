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
from nbd import CONTEXT_BASE_ALLOCATION
import logging


class Extent(object):
    def __init__(self):
        self.data = False
        self.zero = False
        self.length = 0
        self.offset = 0


class _ExtentObj(object):
    def __init__(self):
        self.length = None
        self.type = None


class ExtentHandler(object):
    """Query extent information about allocated and
    zeroed regions from the NBD server started by
    libvirt/qemu

    This implementation should return the same
    extent information as nbdinfo or qemu-img map
    """

    def __init__(self, nbdFh, metaContext, backupSocket):
        self.useQemu = False
        if nbdFh.__class__.__name__ == "qemuHelper":
            self.useQemu = True

        self._socket = backupSocket
        self._nbdFh = nbdFh
        self._extentEntries = []
        if metaContext is None:
            self._metaContext = CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = metaContext

        logging.debug("Meta context: %s", self._metaContext)
        self._maxRequestBlock = 4294967295
        self._align = 512

    def _getExtentCallback(self, metacontext, offset, entries, status):
        """Callback function called by libnbd for each extent
        that is returned
        """
        logging.debug("Metacontext is: %s", metacontext)
        logging.debug("Offset is: %s", offset)
        logging.debug("Status is: %s", status)
        if metacontext != self._metaContext:
            logging.error("Meta context does not match")
            return
        for entry in entries:
            self._extentEntries.append(entry)
        logging.debug("entries: %s", len(self._extentEntries))

    def _setRequestAligment(self):
        align = self._nbdFh.get_block_size(0)
        if align == 0:
            align = self._align
        return self._maxRequestBlock - align + 1

    def queryExtents(self):
        """Query extents either via qemu or custom extent
        handler
        """
        if self.useQemu:
            return self.queryExtentsQemu()

        return self.queryExtentsNbd()

    def queryExtentsQemu(self):
        """Use qemu-img map to query extents from nbd
        server
        """
        extents = []
        for extent in self._nbdFh.map(self._socket):
            extentObj = Extent()
            extentObj.data = bool(extent["data"])
            extentObj.offset = extent["start"]
            extentObj.length = extent["length"]
            extents.append(extentObj)

        logging.debug("Got %s extents from qemu command", len(extents))

        return extents

    def _extentsToObj(self):
        """Go through extents and create a list of extent
        objects
        """
        extentSizes = self._extentEntries[0::2]
        extentTypes = self._extentEntries[1::2]
        assert len(extentSizes) == len(extentTypes)
        ct = 0
        extentList = []
        while ct < len(extentSizes):
            extentObj = _ExtentObj()
            extentObj.length = extentSizes[ct]
            extentObj.type = extentTypes[ct]
            extentList.append(extentObj)
            ct += 1

        return extentList

    def _unifyExtents(self, extentObjects):
        """Unify extents. If a sequence of extents has the
        same type (data or zero) it is better to unify them
        into a bigger block, so during backup, less requests
        to the nbd server have to be sent
        """
        logging.debug("Attempting to unify %s extents", len(extentObjects))
        cur = None
        for myExtent in extentObjects:
            if cur is None:
                cur = myExtent
            elif cur.type == myExtent.type:
                cur.length += myExtent.length
            else:
                yield cur
                cur = myExtent

        yield cur

    def queryExtentsNbd(self):
        """Request used blocks/extents from the nbd service"""
        maxRequestLen = self._setRequestAligment()
        offset = 0
        size = self._nbdFh.get_size()
        logging.debug("Size returned from NDB server: %s", size)
        lastExtentLen = len(self._extentEntries)
        while offset < size:
            if size < maxRequestLen:
                request_length = size
            else:
                request_length = min(size - offset, maxRequestLen)
            logging.debug("Block status request length: %s", request_length)
            self._nbdFh.block_status(request_length, offset, self._getExtentCallback)
            if len(self._extentEntries) == 0:
                logging.error("No extents found")
                return False

            offset += sum(self._extentEntries[lastExtentLen::2])
            lastExtentLen = len(self._extentEntries)

        logging.debug("Extents: %s", self._extentEntries)
        logging.debug("Got %s extents", len(self._extentEntries[::2]))

        return self._extentsToObj()

    def queryBlockStatus(self, extentList=None):
        """Check the status for each extent, whether if it is
        real data or zeroes, return a list of extent objects

        The extent types are as follows:

        For full backup:
            case 0  ("allocated")
            case 1: ("hole")
            case 2: ("zero")
            case 3: ("hole,zero")
        For checkpoint based inc/diff:
            case 0: ("clean")
            case 1: ("dirty")
        """
        if self.useQemu is True:
            return self.queryExtentsQemu()

        extentList = []
        start = 0
        for extent in self._unifyExtents(self.queryExtentsNbd()):
            extObj = Extent()
            if self._metaContext == CONTEXT_BASE_ALLOCATION:
                assert extent.type in (0, 1, 2, 3)
                if extent.type == 0:
                    extObj.data = True
                if extent.type == 1:
                    extObj.data = False
                elif extent.type == 2:
                    extObj.data = True
                elif extent.type == 3:
                    extObj.data = False
            else:
                assert extent.type in (0, 1)
                extObj.data = bool(extent.type)

            extObj.offset = start
            extObj.length = extent.length
            extentList.append(extObj)
            start += extent.length

        logging.debug("Returning extent list with %s objects", len(extentList))
        return extentList
