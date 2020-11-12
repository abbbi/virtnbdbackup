import sh
import json

class qemuHelper(object):

    """Docstring for qemuHelper. """
    def __init__(self,exportName, host="localhost", port="10809", metaContext="base:allocation"):
        """TODO: to be defined.

        :host: TODO
        :port: TODO

        """
        self._exportName = exportName
        self._host = host
        self._port = port

        self.qemuImg = sh.Command("qemu-img")

    def map(self):
        extentMap = self.qemuImg("map", "--output", "json", "nbd://%s:%s/%s" % (
            self._host,
            self._port,
            self._exportName
        )).stdout
        return json.loads(extentMap)
