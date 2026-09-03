"""Built-in output target plugins."""

from libvirtnbdbackup.output.target.plugins.directory import Directory
from libvirtnbdbackup.output.target.plugins.zip import Zip
from libvirtnbdbackup.output.target.plugins.null import Null

__all__ = ["Directory", "Zip", "Null"]
