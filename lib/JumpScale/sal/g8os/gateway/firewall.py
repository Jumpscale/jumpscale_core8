from JumpScale.sal.g8os.gateway import templates
import ipaddress


class Network:
    def __init__(self, iface, cidr):
        self.iface = iface
        ipiface = ipaddress.IPv4Interface(cidr)
        self.ipaddress = str(ipiface.ip)
        self.subnet = str(ipiface.network)


class Firewall:
    def __init__(self, container, publicnetwork, privatenetworks, forwards):
        '''

        '''
        self.container = container
        self.publicnetwork = publicnetwork
        self.privatenetworks = privatenetworks
        self.forwards = forwards

    def apply_rules(self):
        # nftables
        nftables = templates.render('nftables.conf',
                                    privatenetworks=self.privatenetworks,
                                    publicnetwork=self.publicnetwork,
                                    portforwards=self.forwards)
        self.container.upload_content('/etc/nftables.conf', nftables)
        job = self.container.client.system('nft -f /etc/nftables.conf').get()
        if job.state != 'SUCCESS':
            raise RuntimeError("Failed to apply nftables {} {}".format(job.stdout, job.stderr))
