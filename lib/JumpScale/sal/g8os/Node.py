from JumpScale import j
from JumpScale.sal.g8os.Disk import Disks, DiskType
from JumpScale.sal.g8os.StoragePool import StoragePools
from io import BytesIO
from collections import namedtuple
import re


Mount = namedtuple('Mount', ['device', 'mountpoint', 'fstype', 'options', 'dump', 'mpass'])


class Node:
    """Represent a G8OS Server"""

    def __init__(self, addr, port=6379, password=None):
        # g8os client to talk to the node
        self._client = j.clients.g8core.get(host=addr, port=port, password=password)
        self.addr = addr
        self.port = port
        self.disks = Disks(self)
        self.storagepools = StoragePools(self)

    @property
    def client(self):
        return self._client

    def _eligible_fscache_disk(self, disks):
        """
        return the first disk that is eligible to be used as filesystem cache
        First try to find a SSH disk, otherwise return a HDD
        """
        # Pick up the first ssd
        usedisks = []
        for pool in (self._client.btrfs.list() or []):
            for device in pool['devices']:
                usedisks.append(device['path'])
        for disk in disks[::-1]:
            if disk.devicename in usedisks:
                disks.remove(disk)
                continue
            if disk.type in [DiskType.ssd, DiskType.nvme]:
                return disk
            elif disk.type == DiskType.cdrom:
                disks.remove(disk)
        # If no SSD found, pick up the first disk
        return disks[0]

    def _mount_fscache(self, storagepool):
        """
        mount the fscache storage pool and copy the content of the in memmory fs inside
        """
        storagepool.umount()

        # saving /tmp/ contents
        self._client.bash("mkdir -p /tmpbak").get()
        self._client.bash("cp -arv /tmp/* /tmpbak/").get()

        # mount /tmp
        storagepool.mount('/tmp')

        # restoring /tmp
        self._client.bash("cp -arv /tmpbak/* /tmp/").get()
        self._client.bash("rm -rf /tmpbak").get()

    def ensure_persistance(self):
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
            if sp.name == 'fscache':
                fscache_sp = sp

        # create the storage pool if we don't have one yet
        if fscache_sp is None:
            disk = self._eligible_fscache_disk(disks)
            fscache_sp = self.storagepools.create('fscache', devices=[disk.devicename], metadata_profile='single', data_profile='single')

        # mount the storage pool
        self._mount_fscache(fscache_sp)
        return fscache_sp

    def list_mounts(self):
        def unescape(match):
            # unescape spaces or other chars in /proc/mounts
            return chr(int(match.group()[1:], 8))

        mounts = BytesIO()
        self.client.filesystem.download('/proc/mounts', mounts)
        allmounts = []
        for mountline in mounts.getvalue().decode('utf8').splitlines():
            mount = mountline.split()
            for idx, option in enumerate(mount):
                mount[idx] = re.sub('\\\\0\d{2}', unescape, option)
            allmounts.append(Mount(*mount))
        return allmounts

    def __str__(self):
        return "Node <{host}:{port}>".format(
            host=self.addr,
            port=self.port,
        )

    def __repr__(self):
        return str(self)
