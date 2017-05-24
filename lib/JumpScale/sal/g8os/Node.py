from JumpScale import j
from JumpScale.sal.g8os.Disk import Disks, DiskType
from JumpScale.sal.g8os.Container import Containers
from JumpScale.sal.g8os.StoragePool import StoragePools
from collections import namedtuple
from datetime import datetime
import netaddr

Mount = namedtuple('Mount', ['device', 'mountpoint', 'fstype', 'options'])


class Node:
    """Represent a G8OS Server"""

    def __init__(self, addr, port=6379, password=None):
        # g8os client to talk to the node
        self._client = j.clients.g8core.get(host=addr, port=port, password=password)
        self._client.timeout = 120
        self._storageAddr = None
        self.addr = addr
        self.port = port
        self.disks = Disks(self)
        self.storagepools = StoragePools(self)
        self.containers = Containers(self)

    @classmethod
    def from_ays(cls, service):
        return cls(
            addr=service.model.data.redisAddr,
            port=service.model.data.redisPort,
            password=service.model.data.redisPassword or None
        )

    @property
    def client(self):
        return self._client

    @property
    def name(self):
        def get_nic_hwaddr(nics, name):
            for nic in nics:
                if nic['name'] == name:
                    return nic['hardwareaddr']

        defaultgwdev = self.client.bash("ip route | grep default | awk '{print $5}'").get().stdout.strip()
        nics = self.client.info.nic()
        if defaultgwdev:
            macgwdev = get_nic_hwaddr(nics, defaultgwdev)
        if not macgwdev:
            raise AttributeError("name not find for node {}".format(self))
        return macgwdev.replace(":", '')

    @property
    def storageAddr(self):
        if not self._storageAddr:
            nic_data = self.client.info.nic()
            for nic in nic_data:
                if nic['name'] == 'backplane':
                    for ip in nic['addrs']:
                        network = netaddr.IPNetwork(ip['addr'])
                        if network.version == 4:
                            self._storageAddr = network.ip.format()
                            return self._storageAddr
            self._storageAddr = self.addr
        return self._storageAddr

    def _eligible_fscache_disk(self, disks):
        """
        return the first disk that is eligible to be used as filesystem cache
        First try to find a SSH disk, otherwise return a HDD
        """
        priorities = [DiskType.ssd, DiskType.hdd, DiskType.nvme]
        eligible = {t: [] for t in priorities}
        # Pick up the first ssd
        usedisks = []
        for pool in (self._client.btrfs.list() or []):
            for device in pool['devices']:
                usedisks.append(device['path'])
        for disk in disks[::-1]:
            if disk.devicename in usedisks or len(disk.partitions) > 0:
                continue
            if disk.type in priorities:
                eligible[disk.type].append(disk)
        # pick up the first disk according to priorities
        for t in priorities:
            if eligible[t]:
                return eligible[t][0]
        else:
            raise RuntimeError("cannot find eligible disks for the fs cache")

    def _mount_fscache(self, storagepool):
        """
        mount the fscache storage pool and copy the content of the in memmory fs inside
        """
        mountedpaths = [mount.mountpoint for mount in self.list_mounts()]
        containerpath = '/var/cache/containers'
        if containerpath not in mountedpaths:
            if storagepool.exists('containercache'):
                storagepool.delete('containercache')
            fs = storagepool.create('containercache')
            self.client.disk.mount(storagepool.devicename, containerpath, ['subvol={}'.format(fs.subvolume)])
        logpath = '/var/log'
        if logpath not in mountedpaths:
            # logs is empty filesystem which we create a snapshot on to store logs of current boot
            snapname = '{:%Y-%m-%d-%H-%M}'.format(datetime.now())
            fs = storagepool.get('logs')
            snapshot = fs.create(snapname)
            self.client.bash('mkdir /tmp/log && mv /var/log/* /tmp/log/')
            self.client.disk.mount(storagepool.devicename, logpath, ['subvol={}'.format(snapshot.subvolume)])
            self.client.bash('mv /tmp/log/* /var/log/').get()
            self.client.logger.reopen()
            # startup syslogd and klogd
            self.client.system('syslogd -n -O /var/log/messages')
            self.client.system('klogd -n')

    def ensure_persistance(self, name='fscache'):
        """
        look for a disk not used,
        create a partition and mount it to be used as cache for the g8ufs
        set the label `fs_cache` to the partition
        """
        disks = self.disks.list()
        if len(disks) <= 0:
            # if no disks, we can't do anything
            return

        # check if there is already a storage pool with the fs_cache label
        fscache_sp = None
        for sp in self.storagepools.list():
            if sp.name == name:
                fscache_sp = sp
                break

        # create the storage pool if we don't have one yet
        if fscache_sp is None:
            disk = self._eligible_fscache_disk(disks)
            fscache_sp = self.storagepools.create(name, devices=[disk.devicename], metadata_profile='single', data_profile='single', overwrite=True)
        fscache_sp.mount()
        try:
            fscache_sp.get('logs')
        except ValueError:
            fscache_sp.create('logs')

        # mount the storage pool
        self._mount_fscache(fscache_sp)
        return fscache_sp

    def list_mounts(self):
        allmounts = []
        for mount in self.client.info.disk():
            allmounts.append(Mount(mount['device'],
                                   mount['mountpoint'],
                                   mount['fstype'],
                                   mount['opts']))
        return allmounts

    def __str__(self):
        return "Node <{host}:{port}>".format(
            host=self.addr,
            port=self.port,
        )

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        a = "{}:{}".format(self.addr, self.port)
        b = "{}:{}".format(other.addr, other.port)
        return a == b

    def __hash__(self):
        return hash((self.addr, self.port))
