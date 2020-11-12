import nbd

class nbdClient(object):

    """Docstring for nbdClient. """

    def __init__(self, exportName, metaContext, host="localhost", port="10809"):
        """TODO: to be defined.

        :host: TODO
        :port: TODO

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
        self._nbdHandle.add_meta_context(self._metaContext)
        self._nbdHandle.set_export_name(self._exportName)
        self._nbdHandle.connect_tcp(self._host,self._port)

        return self._nbdHandle
