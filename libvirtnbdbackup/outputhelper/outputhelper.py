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
import os
import sys
import zipfile
import logging

from datetime import datetime

log = logging.getLogger(__name__)


class outputHelper:
    """Directs output stream to either regular directory or
    zipfile. If other formats are added class should be
    used as generic wrapper for open()/write()/close() functions.

    Currently only used for zip file creation and creating
    the target output directory.
    """

    class Directory:
        """Backup target directory"""

        def __init__(self, targetDir):
            self.targetDir = targetDir
            self._makeDir()

        def _makeDir(self):
            if os.path.exists(self.targetDir):
                if not os.path.isdir(self.targetDir):
                    log.error("Specified target is a file, not a directory")
                    raise SystemExit(1)
            if not os.path.exists(self.targetDir):
                try:
                    os.makedirs(self.targetDir)
                except OSError as e:
                    log.error("Unable to create target directory: %s", e)
                    raise SystemExit(1) from e

    class Zip:
        """Backup to zip file"""

        def __init__(self):
            self.zipStream = None
            self.zipFileStream = None

            log.info("Writing zip file stream to stdout")
            try:
                self.zipStream = zipfile.ZipFile(
                    sys.stdout.buffer, "x", zipfile.ZIP_STORED
                )
            except zipfile.error as e:
                log.error("Error setting up zip stream: %s", e)
                raise

        def open(self, fileName):
            """Open wrapper"""
            zipFile = zipfile.ZipInfo(
                filename=fileName,
            )
            now = datetime.now()
            zipFile.date_time = now.replace(microsecond=0).timetuple()
            zipFile.compress_type = zipfile.ZIP_STORED

            try:
                self.zipFileStream = self.zipStream.open(zipFile, "w", force_zip64=True)
                return self.zipFileStream
            except zipfile.error as e:
                raise RuntimeError(f"Unable to open zip stream: {e}") from e

            return False

        def close(self):
            """Close wrapper"""
            return self.zipFileStream.close()

        def write(self, data):
            """Write wrapper"""
            return self.zipFileStream.write(data)
