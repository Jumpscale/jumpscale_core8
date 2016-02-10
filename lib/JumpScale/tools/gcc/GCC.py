
from JumpScale import j
from JumpScale.tools.develop.DevelopTools import DebugSSHNode


class GCC(object):

    def __init__(self):
        super(GCC, self).__init__()

    def get(self, nodes=[]):
        """
        define which nodes to init,
        format = ["localhost", "ovh4", "anode:2222", "192.168.6.5:23"]
        this will be remembered in local redis for further usage
        if node = [], previously defined node will be used

        make sure nodes have your SSH key authorized before using there
        can do this with
        j.tools.gcc.authorizeNode(addr,passwd,keyname,login="root",port=22)

        """
        return GCC_Mgmt(nodes)

    def authorizeNode(self, addr, passwd, keyname, login="root", port=22):
        j.tools.executor.getSSHBased(addr=addr, port=port, login=login, passwd=passwd, debug=False, checkok=True, allow_agent=True, look_for_keys=True, pushkey=keyname)


class GCC_Mgmt():

    def __init__(self, nodes=[]):
        if len(nodes) > 0:
            self.init(nodes=nodes)
        self.__jslocation__ = "j.tools.gcc"
        self._host_nodes = []
        self._docker_nodes = []

    def _parseNode(self, nodes):
        nodesObjs = []
        for item in nodes.split(","):
            if item.find(":") != -1:
                addr, sshport = item.split(":")
                addr = addr.strip()
                sshport = int(sshport)
            else:
                addr = item.strip()
                sshport = 22 if addr != "localhost" else 0
            nodesObjs.append(DebugSSHNode(addr, sshport))
        return nodesObjs

    def init(self, nodes=[]):
        """
        define which nodes to init,
        format = ["localhost", "ovh4", "anode:2222", "192.168.6.5:23"]
        this will be remembered in local redis for further usage
        """
        if not j.data.types.list.check(nodes):
            nodes = [nodes]
        j.core.db.set("gcc.host_nodes", ','.join(nodes))

    @property
    def host_nodes(self):
        """
        node object that represent the host machines
        """
        if self._docker_nodes == []:
            if j.core.db.get("gcc.host_nodes") == None:
                self.init()
            nodes = j.core.db.get("gcc.host_nodes").decode()
            self._host_nodes = self._parseNode(nodes)
        return self._host_nodes

    @property
    def docker_nodes(self):
        """
        node object that represent the docker container where all
        the acutal apps are installed
        """
        if self._docker_nodes == []:
            if j.core.db.get("gcc.docker_nodes") == None:
                self.init()
            nodes = j.core.db.get("gcc.docker_nodes").decode()
            self._docker_nodes = self._parseNode(nodes)
        return self._docker_nodes

    def install(self, pubkey):
        containers = []
        for i, node in enumerate(self.host_nodes):
            weave_peer = node[0].addr if i > 0 else None
            print("Prepare host %s" % node.addr)
            self._installHostApp(node, weave_peer)
            print("Create docker container on %s" % node.addr)
            ssh_port = node.cuisine.docker.ubuntu(name='gcc-%d' % i, pubkey=pubkey)
            containers.append("%s:%s" % (node.addr, ssh_port))

        j.core.db.set("gcc.docker_nodes", ','.join(containers))

        print('All host nodes ready.')
        print('Start installations dockers')
        for i, node in enumerate(self.docker_nodes):
            self._installDockerApps(node)

    def _installHostApp(self, node, weave_peer):
        node.cuisine.installerdevelop.jumpscale8()
        node.cuisine.installer.docker()
        node.cuisine.builder.weave(start=True, peer=weave_peer)

    def _installDockerApps(self, node, force=False):
        node.cuisine.installerdevelop.jumpscale8(force=force)

        node.cuisine.builder.caddy(ssl=True, start=True, dns=None, force=force)
        cfg = node.cuisine.file_read("$cfgDir/caddy/caddyfile.conf")
        cfg += """
proxy /etcd localhost:2379 localhost:4001 {
    without /etcd
}

proxy /storex localhost:8090 {
    without /storex
}
"""
        node.cuisine.systemd.start('caddy')

        node.cuisine.builder.etcd(start=True, force=force)
        node.cuisine.builder.skydns(start=True, force=force)
        node.cuisine.builder.aydostore(start=True, addr='127.0.0.1:8090', backend="$varDir/aydostor", force=force)
        node.cuisine.builder.agentcontroller(start=True, force=force)

    def healthcheck(self):
        """
        """
        #@todo (*3*) implement some healthchecks done over agentcontrollers
        #- check diskpace
        #- check cpu
        #- check that 3 are there
        #- check that weave network is intact
        #- check sycnthing is up to date
        #- port checks ...

    def nameserver(self, login, passwd):
        """
        credentials to etcd to allow management of DNS records
        """
        return GCC_Nameserver(self, login, passwd)

    def aydostor(self, login, passwd):
        return GCC_aydostor(self, login, passwd)


class GCC_Nameserver():
    """
    define easy to use interface on top of nameserver management
    """

    def __init__(self, manager, login, passwd):
        self.manager = manager
        self.login = login
        self.passwd = passwd

    def ns_addHost(addr, dnsinfo):  # to be further defined
        #@todo use https over caddy to speak to etcd to configure skydns, maybe clients do already exist?
        pass


class GCC_aydostor():
    """
    define easy to use interface on top of aydostor (use aydostor client, needs to be separate client in js8)
    """

    def __init__(self, manager, login, passwd):
        self.manager = manager
        self.login = login
        self.passwd = passwd

    def ns_addHost(addr, dnsinfo):  # to be further defined
        pass
        #@todo use https over caddy to speak to etcd to configure skydns
