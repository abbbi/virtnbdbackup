"""
Copyright (C) 2025  Michael Ablassmeier <abi@grinser.de>

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

from typing import Optional, Union, Literal
from argparse import Namespace


class TargetPlugin:
    """Plugin base class"""

    def __init__(self, args: Optional[Namespace] = None):
        raise NotImplementedError

    def open(
        self,
        targetFile: str,
        mode: Union[Literal["w"], Literal["wb"], Literal["rb"], Literal["r"]] = "wb",
    ):
        """open"""
        raise NotImplementedError

    def close(self):
        """close"""
        raise NotImplementedError

    def checksum(self):
        """checksum"""
        raise NotImplementedError

    def write(self, data):
        """write"""
        raise NotImplementedError

    def create(self, targetDir: str):
        """create"""
        raise NotImplementedError

    def rename(self, targetFilePartial: str, targetFile: str):
        """rename file"""
        raise NotImplementedError

    def exists(self, fileName: str):
        """check if file exists"""
        raise NotImplementedError

    def empty(self):
        """check if target is empty"""
        raise NotImplementedError
