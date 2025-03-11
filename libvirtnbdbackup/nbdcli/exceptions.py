"""
Exceptions
"""


class NbdClientException(Exception):
    """Nbd exceptions"""


class NbdConnectionError(NbdClientException):
    """Connection failed"""


class NbdConnectionTimeout(NbdClientException):
    """Connection timed out"""
