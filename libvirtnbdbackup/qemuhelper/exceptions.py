"""
    Exceptions
"""


class QemuHelperError(Exception):
    """Errors during qemu helper"""


class NbdServerProcessError(QemuHelperError):
    """Unable to start nbd server for offline backup"""
