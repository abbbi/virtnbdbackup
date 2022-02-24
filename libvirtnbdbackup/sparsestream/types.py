"""
Sparsestream format description
"""


class SparseStreamTypes:
    """Sparse stream format

    META:   start of meta information header
    DATA:   data block marker
    ZERO:   zero block marker
    STOP:   stop block marker
    TERM:   termination identifier
    FRAME:  assembled frame
    FRAME_LEN: length of frame

    Stream format
    =============

    Stream is composed of one of more frames.

    Meta frame
    ----------
    Stream metadata, must be the first frame.

    "meta" space start length "\r\n" <json-payload> \r\n

    Metadata keys in the json payload:

    - virtual-size: image virtual size in bytes
    - data-size: number of bytes in data frames
    - date: ISO 8601 date string

    Data frame
    ----------
    The header is followed by length bytes and terminator.
    "data" space start length "\r\n" <length bytes> "\r\n"

    Zero frame
    ----------
    A zero extent, no payload.
    "zero" space start length "\r\n"

    Stop frame
    ----------
    Marks the end of the stream, no payload.
    "stop" space start length "\r\n"

    Regular stream Example
    -------
    meta 0000000000000000 0000000000000083\r\n
    {
        [.]]
    }\r\n
    data 0000000000000000 00000000000100000\r\n
    <1 MiB bytes>\r\n
    zero 0000000000100000 00000000040000000\r\n
    data 0000000040100000 00000000000001000\r\n
    <4096 bytes>\r\n
    stop 0000000000000000 00000000000000000\r\n


    Compressed stream:
    -------
    Ends with compression marker:
    stop 0000000000000000 00000000000000000\r\n
    <json payload with compressed block sizes>\r\n
    comp 0000000000000000 00000000000000010\r\n
    """

    def __init__(self):
        self.META = b"meta"
        self.DATA = b"data"
        self.COMP = b"comp"
        self.ZERO = b"zero"
        self.STOP = b"stop"
        self.TERM = b"\r\n"
        self.FRAME = b"%s %016x %016x" + self.TERM
        self.FRAME_LEN = len(self.FRAME % (self.STOP, 0, 0))
