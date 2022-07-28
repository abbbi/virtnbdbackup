"""
    Exceptions
"""


class virtHelperError(Exception):
    """Errors during libvirt helper"""


class domainNotFound(virtHelperError):
    """Cant find domain"""


class connectionFailed(virtHelperError):
    """Cant connect libvirtd domain"""


class startBackupFailed(virtHelperError):
    """Cant start backup operation"""
