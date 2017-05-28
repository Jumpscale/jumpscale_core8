import signal
import time

from JumpScale.sal.g8os.gateway import templates


DNSMASQ = '/bin/dnsmasq --conf-file=/etc/dnsmasq.conf -d'


class DHCP:
    def __init__(self, container, domain, dhcps):
        self.container = container
        self.domain = domain
        self.dhcps = dhcps

    def apply_config(self):
        dnsmasq = templates.render('dnsmasq.conf', domain=self.domain, dhcps=self.dhcps)
        self.container.upload_content('/etc/dnsmasq.conf', dnsmasq)

        dhcp = templates.render('dhcp', dhcps=self.dhcps)
        self.container.upload_content('/etc/dhcp', dhcp)

        for process in self.container.client.process.list():
            if 'dnsmasq' in process['cmdline']:
                self.container.client.process.kill(process['pid'], signal.SIGHUP)
                return

        cmd = self.container.client.system(DNSMASQ)
        # check if command is still running after 2 seconds
        time.sleep(2)

        for job in self.container.client.job.list():
            if job['cmd']['id'] == cmd.id:
                return

        raise RuntimeError('Failed to run dnsmasq')









