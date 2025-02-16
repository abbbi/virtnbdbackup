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
from typing import List, Any, Generator, Dict
from nbd import CONTEXT_BASE_ALLOCATION
from libvirtnbdbackup.objects import Extent, _ExtentObj

log = logging.getLogger("extenthandler")


class ExtentHandler:
    """Query extent information about allocated and
    zeroed regions from the NBD server started by libvirt/qemu

    This implementation should return the same
    extent information as nbdinfo or qemu-img map
    """

    def __init__(self, nbdFh, cType) -> None:
        self.useQemu = False
        if nbdFh.__class__.__name__ == "util":
            self.useQemu = True
        self._nbdFh = nbdFh
        self._cType = cType
        self._extentEntries: Dict = {}
        if cType.metaContext == "":
            self._metaContext = CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = cType.metaContext

        self.contexts = []
        self.offset = 0
        contexts = self._nbdFh.nbd.get_nr_meta_contexts()
        log.debug("NBD server exports [%d] metacontexts:", contexts)
        for i in range(0, contexts):
            ctx = self._nbdFh.nbd.get_meta_context(i)
            self._extentEntries[ctx] = []
            self.contexts.append(ctx)
        log.debug(self.contexts)

        log.debug("Primary meta context for backup: %s", self._metaContext)
        self._maxRequestBlock: int = 4294967295
        self._align: int = 512

    def _getExtentCallback(
        self, metacontext: str, offset: int, entries: List, status: str
    ) -> None:
        """Callback function called by libnbd for each extent
        that is returned
        """
        log.debug("Metacontext is: %s", metacontext)
        log.debug("Offset is: %s", offset)
        log.debug("Status is: %s", status)
        for entry in entries:
            self._extentEntries[metacontext].append(entry)
        log.debug("entries: %s", len(self._extentEntries[metacontext]))
        for x in self._extentEntries[metacontext][::2]:
            self.offset += x
        log.debug("Processed offsets: %s", self.offset)

    def _setRequestAligment(self) -> int:
        """Align request size to nbd server"""
        align = self._nbdFh.nbd.get_block_size(0)
        if align == 0:
            align = self._align
        return self._maxRequestBlock - align + 1

    def queryExtents(self) -> List[Any]:
        """Query extents either via qemu or custom extent
        handler
        """
        if self.useQemu:
            return self.queryExtentsQemu()

        return self.queryExtentsNbd()

    def queryExtentsQemu(self) -> List[Any]:
        """Use qemu utils to query extents from nbd
        server
        """
        extents = []
        for extent in self._nbdFh.map(self._cType):
            extentObj = Extent(
                self.setBlockType(extent["type"]), extent["offset"], extent["length"]
            )
            extents.append(extentObj)

        log.debug("Got %s extents from qemu command", len(extents))

        return extents

    def _extentsToObj(self) -> List[_ExtentObj]:
        """Go through extents and create a list of extent
        objects
        """
        extentList = []
        for context, values in self._extentEntries.items():
            extentSizes = values[0::2]
            extentTypes = values[1::2]
            assert len(extentSizes) == len(extentTypes)
            ct = 0
            while ct < len(extentSizes):
                extentObj = _ExtentObj(context, extentSizes[ct], extentTypes[ct])
                extentList.append(extentObj)
                ct += 1

        return extentList

    @staticmethod
    def _unifyExtents(extentObjects: List[_ExtentObj]) -> Generator:
        """Unify extents. If a sequence of extents has the
        same type (data or zero) it is better to unify them
        into a bigger block, so during backup, less requests
        to the nbd server have to be sent
        """
        log.debug("Attempting to unify %s extents", len(extentObjects))
        cur = None
        print(extentObjects)
        for myExtent in extentObjects:
            if cur is None:
                cur = myExtent
            elif cur.type == myExtent.type:
                cur.length += myExtent.length
            else:
                yield cur
                cur = myExtent

        yield cur

    def queryExtentsNbd(self) -> List[_ExtentObj]:
        """Request used blocks/extents from the nbd service"""
        maxRequestLen = self._setRequestAligment()
        # log.debug("Size returned from NBD server: %s", size)
        size = self._nbdFh.nbd.get_size()
        while self.offset < size:
            if size < maxRequestLen:
                request_length = size
            else:
                request_length = min(size - self.offset, maxRequestLen)
            log.debug("Block status request length: %s", request_length)
            self._nbdFh.nbd.block_status(
                request_length, self.offset, self._getExtentCallback
            )

            log.debug("Extents: %s", self._extentEntries)

        return self._extentsToObj()

    def setBlockType(self, context: str, blockType: int) -> bool:
        """Returns block type

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
        data = None
        if context == CONTEXT_BASE_ALLOCATION:
            assert blockType in (0, 1, 2, 3)
            if blockType == 0:
                data = True
            if blockType == 1:
                data = False
            elif blockType == 2:
                data = True
            elif blockType == 3:
                data = False
        else:
            assert blockType in (0, 1)
            data = bool(blockType)

        assert data is not None
        return data

    def overlap(self, extents: List[Extent]) -> List[Extent]:
        """Find overlaps between base allocation and incremental
        bitmap to detect zero regions"""
        overlapping_regions = []
        # Sort extents by their offset
        extents = sorted(extents, key=lambda x: x.offset)

        for i in range(len(extents)):
            start1 = extents[i].offset
            end1 = extents[i].offset + extents[i].length

            for j in range(i + 1, len(extents)):
                start2 = extents[j].offset
                end2 = extents[j].offset + extents[j].length

                if start2 >= end1:
                    break  # No need to check further

                if start1 < end2 and start2 < end1:
                    # Calculate overlap
                    overlap_start = max(start1, start2)
                    overlap_end = min(end1, end2)
                    overlap_length = overlap_end - overlap_start

                    overlapping_regions.append(
                        Extent(
                            context="{extents[i].context} and {extents[j].context}",
                            data=True,
                            offset=overlap_start,
                            length=overlap_length,
                        )
                    )

        return overlapping_regions

    def queryBlockStatus(self) -> List[Extent]:
        """Check the status for each extent, whether if it is
        real data or zeroes, return a list of extent objects
        """
        if self.useQemu is True:
            return self.queryExtentsQemu()

        extents = self.queryExtentsNbd()
        extentList: List[Extent] = []
        start = 0
        for extent in self._unifyExtents(extents):
            extObj = Extent(
                extent.context,
                self.setBlockType(extent.context, extent.type),
                start,
                extent.length,
            )
            extentList.append(extObj)
            start += extent.length

        overlapping_regions = self.overlap(extentList)
        if overlapping_regions:
            log.debug("Overlapping regions:")
            for region in overlapping_regions:
                log.debug(
                    "Overlapping in %s: Start %s, Length %s",
                    region.context,
                    region.offset,
                    region.length,
                )
        else:
            log.debug("No overlapping regions found.")

        log.debug("Returning extent list with %s objects", len(extentList))
        return extentList
