from JumpScale import j

descr = """
gather statistics about disks
"""

organization = "jumpscale"
author = "kristof@incubaid.com"
license = "bsd"
version = "1.0"
category = "disk.monitoring"
period = 300 #always in sec
timeout = period * 0.2
order = 1
enable=True
async=True
queue='process'
log=False

roles = []

def action():
    import statsd
    import psutil

    dcl = j.data.models.system.Disk
    stats = statsd.StatsClient()
    pipe = stats.pipeline()

    disks = j.sal.diskmanager.partitionsFind(mounted=True, prefix='', minsize=0, maxsize=None)

    #disk counters
    counters=psutil.disk_io_counters(True)

    for disk in disks:

        results = {'time_read': 0, 'time_write': 0, 'count_read': 0, 'count_write': 0,
                   'kbytes_read': 0, 'kbytes_write': 0, 
                   'space_free_mb': 0, 'space_used_mb': 0, 'space_percent': 0}
        path = disk.path.replace("/dev/","")

        odisk = dcl()
        old = dcl.find({'path': path})
        odisk.nid = j.application.whoAmI.nid
        odisk.gid = j.application.whoAmI.gid

        if path in counters.keys():
            counter=counters[path]
            read_count, write_count, read_bytes, write_bytes, read_time, write_time=counter
            results['time_read'] = read_time
            results['time_write'] = write_time
            results['count_read'] = read_count
            results['count_write'] = write_count

            read_bytes=int(round(read_bytes/1024,0))
            write_bytes=int(round(write_bytes/1024,0))
            results['kbytes_read'] = read_bytes
            results['kbytes_write'] = write_bytes
            results['space_free_mb'] = int(round(disk.free))
            results['space_used_mb'] = int(round(disk.size-disk.free))
            results['space_percent'] = int(round((float(disk.size-disk.free)/float(disk.size)),2))

            if old:
                old = old[0].to_dict()
                for key,value in disk.__dict__.items():
                    same = old[key] == value
                    odisk[key]=value
                    if not same:
                        changed = True
                if changed:
                    print("Disk %s changed" % (path))
                    old.delete()
                    odisk.save()

        for key, value in results.items():
            pipe.gauge("%s_%s_disk_%s_%s" % (j.application.whoAmI.gid, j.application.whoAmI.nid, path, key), value)

    result = pipe.send()
    return {'results': result, 'errors': []}

if __name__ == '__main__':
    action()
