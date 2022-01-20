import os
import logging
import nbd
from time import sleep

log = logging.getLogger(__name__)


class nbdClient:
    """Helper functions for NBD"""

    def __init__(self, exportName, metaContext, backupSocket):
        """Parameters:
        :exportName: name of nbd export
        :backupSocket: ndb server endpoint
        """
        self._socket = backupSocket
        self._exportName = exportName
        if metaContext is None:
            self._metaContext = nbd.CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = metaContext

        self.maxRequestSize = 33554432
        self.minRequestSize = 65536

        self._connectionHandle = None

        self._nbdHandle = nbd.NBD()

        self.version()

    def version(self):
        log.info("libnbd version: %s", nbd.__version__)

    def getBlockInfo(self):
        """Read maximum request/block size as advertised by the nbd
        server. This is the value which will then be used by default
        """
        maxSize = self._nbdHandle.get_block_size(nbd.SIZE_MAXIMUM)
        if maxSize != 0:
            self.maxRequestSize = maxSize

        log.info("Using Maximum Block size supported by nbd server: %s", maxSize)

    def connect(self):
        """Setup connection to NBD server endpoint, return
        connection handle
        """
        try:
            self._nbdHandle.add_meta_context(self._metaContext)
            self._nbdHandle.set_export_name(self._exportName)
            self._nbdHandle.connect_unix(self._socket)
        except nbd.Error as e:
            log.error("Unable to connect ndb server: %s", e)
            return False

        self.getBlockInfo()

        return self._nbdHandle

    def waitForServer(self):
        """Wait until NBD endpoint connection can be established"""
        logging.info("Waiting until nbd server on socket %s is up.", self._socket)
        retry = 0
        maxRetry = 20
        sleepTime = 1
        while True:
            sleep(sleepTime)
            if retry >= maxRetry:
                logging.error("NBD server connection failed.")
                return False

            if not os.path.exists(self._socket):
                logging.info("Waiting for NBD Server, Retry: %s", retry)
                retry = retry + 1

            connection = self.connect()
            if connection:
                logging.info("Connection to nbd backend succeeded.")
                return connection

            logging.info("Waiting for NBD Server, Retry: %s", retry)
            retry = retry + 1

        return False

    def disconnect(self):
        self._nbdHandle.shutdown()
