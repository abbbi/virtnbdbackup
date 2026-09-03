"""Output target plugin API and built-in plugin registration."""

from libvirtnbdbackup.output.target.base import OutputTarget
from libvirtnbdbackup.output.target.plugins import Directory, Zip, Null
from libvirtnbdbackup.output.target.registry import (
    create,
    create_input,
    names,
    register,
)

register("directory", Directory)
register("zip", Zip)
register("null", Null)

__all__ = ["OutputTarget", "create", "create_input", "names", "register"]
