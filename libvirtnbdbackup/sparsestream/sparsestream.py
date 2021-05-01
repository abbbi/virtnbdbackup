import json
import datetime

class SparseStreamTypes:
    """ Sparse stream format

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

        Example
        -------

        meta 0000000000000000 0000000000000083\r\n
        {
            "virtual-size": 6442450944,
            "data-size": 1288486912,
            "date": "2020-07-09T20:33:34.349705",
            "disk_uuid": "sldf-aldflasfa-llalsdfla-la",
            "incremental": false,
            "stream_version": 1
        }\r\n
        data 0000000000000000 00000000000100000\r\n
        <1 MiB bytes>\r\n
        zero 0000000000100000 00000000040000000\r\n
        ...
        data 0000000040100000 00000000000001000\r\n
        <4096 bytes>\r\n
        stop 0000000000000000 00000000000000000\r\n
    """
    def __init__(self):
        self.META = b"meta"
        self.DATA = b"data"
        self.ZERO = b"zero"
        self.STOP = b"stop"
        self.TERM = b"\r\n"
        self.FRAME = b"%s %016x %016x" + self.TERM
        self.FRAME_LEN = len(self.FRAME % (self.STOP, 0, 0))

class SparseStream:
    """ Sparse Stream
    """
    def __init__(self, version=1):
        """ Stream version set to 1 by default
        """
        self.version = version
        self.types = SparseStreamTypes()

    def dumpMetadata(self, virtualSize, dataSize, diskName, checkpointName, parentCheckpoint, incremental):
        """ First block in backup stream is Meta data information
            about virtual size of the disk beeing backed up

            Dumps Metadata frame to be written at start of stream in
            json format.

                Parameters:
                    virtualSize:(int)       virtual size of disk
                    dataSize:   (int)       used space of disk
                    diskName:   (str)       name of the disk backed up
                    checkpointName:   (str)  checkpoint name
                    parentCheckpoint: (str)  parent checkpoint
                    incremental: (boolean)   wether if backup is incremental

                Returns:
                    json.dumps: (str)   json encoded meta frame
        """
        meta = {
            "virtualSize": virtualSize,
            "dataSize": dataSize,
            "date": datetime.datetime.now().isoformat(),
            "diskName": diskName,
            "checkpointName": checkpointName,
            "parentCheckpoint": parentCheckpoint,
            "incremental": incremental,
            "stream-version": self.version
        }
        return json.dumps(meta, indent=4).encode("utf-8")

    def loadMetadata(self, s):
        """ Load and parse metadata information
                Parameters:
                    s:  (str)   Json string as received during data file read
                Returns:
                    json.loads: (dict)  Decoded json string as python object
        """
        return json.loads(s.decode("utf-8"))

    def writeFrame(self, writer, kind, start, length):
        """ Write backup frame
                Parameters:
                    writer: (fh)    Writer object that implements .write()
        """
        writer.write(self.types.FRAME % (kind, start, length))

    def readFrame(self, reader):
        """ Read backup frame
                Parameters:
                    reader: (fh)    Reader object which implements .read()
        """
        header = reader.read(self.types.FRAME_LEN)
        kind, start, length = header.split(b" ", 2)
        return kind, int(start, 16), int(length, 16)
