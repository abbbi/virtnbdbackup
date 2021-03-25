import nbd

class nbdClient(object):
    """ Helper functions for NBD
    """
    def __init__(self, exportName, metaContext, host="localhost", port="10809"):
        """ Parameters:

        :exportName: name of nbd export
        :host: ndb serer endpoint
        :port: nbd server port
        """
        self._host = host
        self._port = port
        self._exportName = exportName
        if metaContext == None:
            self._metaContext = nbd.CONTEXT_BASE_ALLOCATION
        else:
            self._metaContext = metaContext

        self.maxRequestSize = 33554432
        self.minRequestSize = 65536

        self._connectionHandle = None

        self._nbdHandle = nbd.NBD()

    def connect(self):
        """ Setup connection to NBD server endpoint, return
        connection handle
        """
        self._nbdHandle.add_meta_context(self._metaContext)
        self._nbdHandle.set_export_name(self._exportName)
        self._nbdHandle.connect_tcp(self._host,self._port)

        return self._nbdHandle

    def disconnect(self):
        self._nbdHandle.shutdown()
