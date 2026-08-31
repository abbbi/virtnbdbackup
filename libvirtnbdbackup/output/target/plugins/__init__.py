"""Built-in output target plugins."""

from libvirtnbdbackup.output.target.plugins.directory import Directory
from libvirtnbdbackup.output.target.plugins.zip import Zip

__all__ = ["Directory", "Zip"]
