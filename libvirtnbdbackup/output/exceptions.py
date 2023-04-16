"""
    Exceptions
"""


class OutputException(Exception):
    """Outpuhelper exceptions"""


class OutputOpenException(OutputException):
    """File open failed"""


class OutputCreateDirectory(OutputException):
    """Can't create output directory"""
