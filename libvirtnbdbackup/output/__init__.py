"""Output helper class"""
__title__ = "output"
__version__ = "0.1"

from .target import target

openfile = target.Directory("").open
