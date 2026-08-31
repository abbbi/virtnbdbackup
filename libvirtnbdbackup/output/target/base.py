"""Output target plugin interface."""

from abc import ABC, abstractmethod
from typing import IO, Any, Optional


class OutputTarget(ABC):
    """Interface implemented by output target plugins."""

    @abstractmethod
    def create(self, targetDir: str) -> None:
        """Create a target container or directory."""

    @abstractmethod
    def open(self, targetFile: str, mode: str = "wb") -> IO[Any]:
        """Open a file in the target."""

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Write data to the currently open file."""

    @abstractmethod
    def close(self) -> None:
        """Close the currently open file."""

    @abstractmethod
    def checksum(self) -> Any:
        """Return and reset the checksum for the current file, if supported."""

    def add_file(self, source: str, target: Optional[str] = None) -> None:
        """Add an existing file to the target, if required by the plugin."""

    def add_tree(self, source: str) -> None:
        """Add an existing directory tree, if required by the plugin."""

    def add_stream(self, source: IO[bytes], target: str) -> None:
        """Copy an existing binary stream into the target."""
        self.open(target)
        try:
            while True:
                data = source.read(1024 * 1024)
                if not data:
                    break
                self.write(data)
        finally:
            self.close()

    def finish(self) -> None:
        """Finalize the output target after all files have been written."""
