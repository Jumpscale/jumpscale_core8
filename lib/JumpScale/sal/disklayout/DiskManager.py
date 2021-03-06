from JumpScale import j
import JumpScale.sal.disklayout.mount as mount
import JumpScale.sal.disklayout.lsblk as lsblk
import JumpScale.sal.disklayout.disks as disks

class DiskManager:
    """
     helps you to gather a lot of information about the disks and partitions.
    """
    def __init__(self):
        self.__jslocation__ = "j.sal.disklayout"
        self.disks = []
        self._executor = j.tools.executor.getLocal()

    def set_executor(self, executor):
        self._executor = executor

    def _loadhrd(self, mount):
        hrdpath = j.tools.path.get(mount).joinpath('.disk.hrd')
        if hrdpath.exists():
            return j.data.hrd.get(hrdpath)
        else:
            return None

    def _loaddisks(self, blks):
        """
        Parses the output of command
        `lsblk -abnP -o NAME,TYPE,UUID,FSTYPE,SIZE`

        Output must look like that
        NAME="sda" TYPE="disk" UUID="" FSTYPE="" SIZE="256060514304"
        NAME="sda1" TYPE="part" UUID="1db378f5-4e49-4fb7-8000-051fe77b23ea"
            FSTYPE="btrfs" SIZE="256059465728"
        NAME="sr0" TYPE="rom" UUID="" FSTYPE="" SIZE="1073741312"
        """

        # find temp mounts & remove, they need to be gone, otherwise will get
        # unpredictable results further
        for line in self._executor.execute("mount")[1].split("\n"):
            if " on /tmp" in line:
                mntpoint = line.split(" on ")[1].split(" type", 1)[0].strip()
                self._executor.execute("umount %s" % mntpoint)

        devices = []
        disk = None

        for blk in blks:
            name = blk['NAME']
            if blk['TYPE'] == 'disk':
                disk = disks.DiskInfo(name=name, size=blk['SIZE'], mountpoint=blk[
                                      'MOUNTPOINT'], fstype=blk['FSTYPE'], uuid=blk['UUID'], executor=self._executor)
                devices.append(disk)
            elif blk['TYPE'] == 'part':
                if disk is None:
                    raise Exception(
                        ('Partition "%s" does not have a parent disk' %
                            blk['NAME'])
                    )
                part = disks.PartitionInfo(
                    name, blk['SIZE'],
                    blk['UUID'], blk['FSTYPE'],
                    blk['MOUNTPOINT'], disk
                )
                disk.partitions.append(part)
            else:
                # don't care about outher types.
                disk = None

        return devices

    def getDisks(self):
        """
        Get list of all available disks on machine
        """
        blks = lsblk.lsblk(executor=self._executor)
        devices = self._loaddisks(blks)
        # loading hrds
        for disk in devices:
            for partition in disk.partitions:
                if partition.fstype == 'swap' or\
                        not disks.isValidFS(partition.fstype):
                    continue

                if partition.mountpoint != "" and partition.mountpoint is not None:
                    # partition is already mounted, no need to remount it
                    hrd = self._loadhrd(partition.mountpoint)
                elif partition.fstype:
                    from IPython import embed
                    print("DEBUG NOW getDisks no mounts")
                    embed()
                    p

                    with mount.Mount(partition.name, options='ro') as mnt:
                        hrd = self._loadhrd(mnt.path)

                partition.hrd = hrd

                print("found partition: %s:%s" % (disk, partition))

        def findDisk(devices, name):

            for item in devices:
                if item.name == name:
                    return item
            raise j.exceptions.RuntimeError("could not find disk:%s" % name)

        for device in devices:
            if device.mirror_devices != [] and device.mountpoint == "":
                # find the mountpoint of one the mirrors
                for mir in device.mirror_devices:
                    disk = findDisk(devices, mir)
                    if disk.mountpoint != "":
                        device.mountpoint = disk.mountpoint

        self.disks = devices
        return devices

    def findDisk(self, name="", mountpoint="", caseSensitive=False):
        if self.disks == []:
            self.getDisks()
        for disk in self.disks:
            if not caseSensitive and mountpoint != "" and disk.mountpoint.lower() == mountpoint.lower():
                return disk
            elif caseSensitive and mountpoint != "" and disk.mountpoint == mountpoint:
                return disk
            elif mountpoint == "" and name != "" and name in disk.name:
                return disk
        return None

    def filesystemStat(self, path):
        data = self._executor.execute("df --output='source,size,used,avail' '%s' | tail -1" % path)
        out = ' '.join(data[1].replace('K', '').split())

        fields = out.split(' ')
        values = {
            'root': fields[0],
            'size': int(fields[1]) * 1024,
            'used': int(fields[2]) * 1024,
            'free': int(fields[3]) * 1024,
        }

        return values
