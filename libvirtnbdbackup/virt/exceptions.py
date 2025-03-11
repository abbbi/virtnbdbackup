"""
Exceptions
"""


class virtHelperError(Exception):
    """Errors during libvirt helper"""


class domainNotFound(virtHelperError):
    """Can't find domain"""


class connectionFailed(virtHelperError):
    """Can't connect libvirtd domain"""


class startBackupFailed(virtHelperError):
    """Can't start backup operation"""
