import json
from io import BytesIO
from JumpScale import j


class Containers:
    def __init__(self, node):
        self.node = node

    def list(self):
        containers = []
        for container in self.node.client.container.list().values():
            try:
                containers.append(Container.from_containerinfo(container, self.node))
            except ValueError:
                # skip containers withouth tags
                pass
        return containers

    def get(self, name):
        containers = list(self.node.client.container.find(name).values())
        if not containers:
            raise LookupError("Could not find container with name {}".format(name))
        if len(containers) > 1:
            raise LookupError("Found more than one containter with name {}".format(name))
        return Container.from_containerinfo(containers[0], self.node)

    def create(self, name, flist, hostname=None, mounts=None, nics=None,
               host_network=False, ports=None, storage=None, init_processes=None):
        j.sal.g8os.logger.debug("create container %s", name)
        container = Container(name, self.node, flist, hostname, mounts, nics,
                              host_network, ports, storage, init_processes)
        container.start()
        return container


class Container:
    """G8SO Container"""

    def __init__(self, name, node, flist, hostname=None, mounts=None, nics=None,
                 host_network=False, ports=None, storage=None, init_processes=None):
        """
        TODO: write doc string
        filesystems: dict {filesystemObj: target}
        """
        self.name = name
        self.node = node
        self.mounts = mounts or {}
        self.hostname = hostname
        self.flist = flist
        self.ports = ports or {}
        self.nics = nics or []
        self.host_network = host_network
        self.storage = storage
        self.init_processes = init_processes or []
        self._client = None

        self._ays = None

    @classmethod
    def from_containerinfo(cls, containerinfo, node):
        j.sal.g8os.logger.debug("create container from info")
        arguments = containerinfo['container']['arguments']
        if not arguments['tags']:
            # we don't deal with tagless containers
            raise ValueError("Could not load containerinfo withouth tags")
        return cls(arguments['tags'][0],
                   node,
                   arguments['root'],
                   arguments['hostname'],
                   arguments['mount'],
                   arguments['nics'],
                   arguments['host_network'],
                   arguments['port'],
                   arguments['storage'])

    @classmethod
    def from_ays(cls, service):
        j.sal.g8os.logger.debug("create container from service (%s)", service)
        from JumpScale.sal.g8os.Node import Node
        node = Node.from_ays(service.parent)
        ports = {}
        for portmap in service.model.data.ports:
            source, dest = portmap.split(':')
            ports[int(source)] = int(dest)
        nics = [nic.to_dict() for nic in service.model.data.nics]
        mounts = {}
        for mount in service.model.data.mounts:
            fs_service = service.aysrepo.serviceGet('filesystem', mount.filesystem)
            try:
                sp = node.storagepools.get(fs_service.parent.name)
                fs = sp.get(fs_service.name)
            except KeyError:
                continue
            mounts[fs.path] = mount.target

        container = cls(
            name=service.name,
            node=node,
            mounts=mounts,
            nics=nics,
            hostname=service.model.data.hostname,
            flist=service.model.data.flist,
            ports=ports,
            host_network=service.model.data.hostNetworking,
            storage=service.model.data.storage,
            init_processes=[p.to_dict() for p in service.model.data.initProcesses],
        )
        return container

    @property
    def id(self):
        j.sal.g8os.logger.debug("get container id")
        info = self.info
        if info:
            return info['container']['id']
        return

    @property
    def info(self):
        j.sal.g8os.logger.debug("get container info")
        for containerid, container in self.node.client.container.list().items():
            if self.name in (container['container']['arguments']['tags'] or []):
                container['container']['id'] = int(containerid)
                return container
        return

    @property
    def client(self):
        if self._client is None:
            self._client = self.node.client.container.client(self.id)
        return self._client

    def upload_content(self, remote, content):
        if isinstance(content, str):
            content = content.encode('utf8')
        bytes = BytesIO(content)
        self.client.filesystem.upload(remote, bytes)

    def _create_container(self, timeout=60):
        j.sal.g8os.logger.debug("send create container command to g8os")
        tags = [self.name]
        if self.hostname and self.hostname != self.name:
            tags.append(self.hostname)
        job = self.node.client.container.create(
            root_url=self.flist,
            mount=self.mounts,
            host_network=self.host_network,
            nics=self.nics,
            port=self.ports,
            tags=tags,
            hostname=self.hostname,
            storage=self.storage,
        )

        result = job.get(timeout)
        if result.state != 'SUCCESS':
            raise RuntimeError('failed to create container %s' % result.data)
        containerid = json.loads(result.data)
        self._client = self.node.client.container.client(containerid)

    def start(self):
        if not self.is_running():
            j.sal.g8os.logger.debug("start %s", self)
            self._create_container()
            for process in self.init_processes:
                cmd = "{} {}".format(process['name'], ' '.join(process.get('args', [])))
                pwd = process.get('pwd', '')
                stdin = process.get('stdin', '')
                env = {}
                for x in process.get('environment', []):
                    k, v = x.split("=")
                    env[k] = v
                self.client.system(command=cmd, dir=pwd, stdin=stdin, env=env)

    def stop(self):
        if not self.is_running():
            return
        j.sal.g8os.logger.debug("stop %s", self)

        self.node.client.container.terminate(self.id)
        self._client = None

    def is_running(self):
        return self.id is not None

    @property
    def ays(self):
        if self._ays is None:
            from JumpScale.sal.g8os.atyourservice.StorageCluster import ContainerAYS
            self._ays = ContainerAYS(self)
        return self._ays

    def __str__(self):
        return "Container <{}>".format(self.name)

    def __repr__(self):
        return str(self)
