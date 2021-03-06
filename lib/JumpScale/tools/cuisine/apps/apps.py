from JumpScale import j

base = j.tools.cuisine._getBaseClassLoader()


class apps(base):

    def __init__(self, executor, cuisine):
        self._dnsmasq = None
        base.__init__(self, executor, cuisine)

    @property
    def dnsmasq(self):
        # TODO: fix thread safe
        if self._dnsmasq is None:
            self._dnsmasq = j.sal.dnsmasq
            self._dnsmasq._cuisine = self._cuisine
            self._dnsmasq.executor = self._executor
        return self._dnsmasq
