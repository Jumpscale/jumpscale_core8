from JumpScale import j

descr = """
Checks databases' status
"""

organization = "jumpscale"
author = "zains@codescalers.com"
category = "monitor.healthcheck"
license = "bsd"
version = "1.0"

async = True
queue = 'process'
roles = ['master']
enable = True
period = 600

log = True


def action():
    osiscl = j.clients.osis.getByInstance('main')
    status = osiscl.getStatus()
    results = list()
    if status['mongodb'] is False:
        j.errorconditionhandler.raiseOperationalCritical('mongodb status -> halted', 'monitoring', die=False)
        results.append({'message': 'mongodb status -> halted', 'state': 'HALTED', 'category': 'Databases'})
    else:
        results.append({'message': 'mongodb status -> running', 'state': 'OK', 'category': 'Databases'})

    if status['influxdb'] is False:
        j.errorconditionhandler.raiseOperationalCritical('influxdb status -> halted', 'monitoring', die=False)
        results.append({'message': 'influxdb status -> halted', 'state': 'HALTED', 'category': 'Databases'})
    else:
        results.append({'message': 'influxdb status -> running', 'state': 'OK', 'category': 'Databases'})
    return results

if __name__ == "__main__":
    print(action())
