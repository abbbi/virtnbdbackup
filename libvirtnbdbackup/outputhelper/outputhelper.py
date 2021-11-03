import os
import sys
import zipfile
import logging

from datetime import datetime

log = logging.getLogger(__name__)


class dirFunc:
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


class outputHelper:
    class Directory(dirFunc):
        def __init__(self, targetDir):
            self.targetDir = targetDir
            self.fileHandle = None

            self._makeDir()

        def open(self, fileName, mode="w+"):
            targetFile = f"{self.targetDir}/{fileName}"
            try:
                self.fileHandle = open(targetFile, mode)
                return self.fileHandle
            except Exception as e:
                log.error("Unable to open file: %s", e)

            return False

        def close(self):
            return self.fileHandle.close()

        def write(self, data):
            return self.fileHandle.write(data)

    class Zip(dirFunc):
        def __init__(self):
            self.zipStream = None
            self.zipFileStream = None

            log.info("Writing zip file stream to stdout")
            try:
                self.zipStream = zipfile.ZipFile(
                    sys.stdout.buffer, "x", zipfile.ZIP_STORED
                )
            except Exception as e:
                log.error("Error setting up zip stream: %s", e)
                raise

        def open(self, fileName, mode="x"):
            zipFile = zipfile.ZipInfo(
                filename=fileName,
            )
            now = datetime.now()
            zipFile.date_time = now.replace(microsecond=0).timetuple()
            zipFile.compress_type = zipfile.ZIP_STORED

            try:
                self.zipFileStream = self.zipStream.open(zipFile, "w", force_zip64=True)
                return self.zipFileStream
            except Exception as e:
                log.error("Unable to open file: %s", e)

            return False

        def close(self):
            return self.zipFileStream.close()

        def write(self, data, target=None):
            return self.zipFileStream.write(data)
