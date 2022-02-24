"""
    Exceptions
"""


class StreamFormatException(Exception):
    """Wrong metadata header"""


class MetaHeaderFormatException(StreamFormatException):
    """Wrong metadata header"""


class BlockFormatException(StreamFormatException):
    """Wrong metadata header"""


class FrameformatException(StreamFormatException):
    """Frame Format is wrong"""
