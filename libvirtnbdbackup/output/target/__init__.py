"""Output target plugin API and built-in plugin registration."""

from libvirtnbdbackup.output.target.base import OutputTarget
from libvirtnbdbackup.output.target.plugins import Directory, Zip
from libvirtnbdbackup.output.target.registry import create, names, register

register("directory", Directory)
register("zip", Zip)

__all__ = ["OutputTarget", "create", "names", "register"]
