"""Example directory-compatible output target plugin."""

import logging
from typing import IO, Any

from libvirtnbdbackup.output.target.plugins.directory import Directory

log = logging.getLogger("example-directory-output-target")


class ExampleDirectoryTarget(Directory):
    """Directory target that logs each file opened by the backup."""

    def open(self, targetFile: str, mode: str = "wb") -> IO[Any]:
        log.info("Example plugin opening target file: [%s]", targetFile)
        return super().open(targetFile, mode)
