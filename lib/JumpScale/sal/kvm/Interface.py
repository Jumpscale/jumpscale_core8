from JumpScale import j
from xml.etree import ElementTree
from BaseKVMComponent import BaseKVMComponent
import random

class Interface(BaseKVMComponent):

    @staticmethod
    def generate_mac():
        mac = [0x00, 0x16, 0x3e,
               random.randint(0x00, 0x7f),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff)]
        return ':'.join(map(lambda x: '%02x' % x, mac))

    def __init__(self, controller, name, bridge, mac=None, interface_rate=None, burst=None, source=None):

        self.controller = controller
        self.name = name
        self.bridge = bridge
        self.qos = not (interface_rate is None)
        self.interface_rate = str(interface_rate)
        self.burst = None
        if not (interface_rate is None):
            self.burst = str(int(interface_rate * 0.1))
        self._source = source
        self.mac = mac if mac else Interface.generate_mac()

    def destroy(self):
        """
        Delete interface and port related to certain machine.

        @bridge str: name of bridge
        @name str: name of port and interface to be deleted
        """
        return self.controller.executor.execute('ovs-vsctl del-port %s %s' % (self.bridge.name, self.name))

    def qos(self, qos, burst=None):
        """
        Limit the throughtput into an interface as a for of qos.

        @interface str: name of interface to limit rate on
        @qos int: rate to be limited to in Kb
        @burst int: maximum allowed burst that can be reached in Kb/s
        """
        # TODO: *1 spec what is relevant for a vnic from QOS perspective, what can we do
        # goal is we can do this at runtime
        self.controller.executor.execute(
            'ovs-vsctl set interface %s ingress_policing_rate=%d' % (self.name, qos))
        if not burst:
            burst = int(qos * 0.1)
        self.controller.executor.execute(
            'ovs-vsctl set interface %s ingress_policing_burst=%d' % (self.name, burst))

    @classmethod
    def from_xml(cls, controller, xml):
        interface = ElementTree.fromstring(xml)
        name = interface.find('virtualport').find('parameters').get('profileid')
        bridge = interface.find('source').get('bridge')
        bandwidth = interface.findall('bandwidth')
        if bandwidth:
            interface_rate = bandwidth[0].find('inbound').get('average')
            burst = bandwidth[0].find('inbound').get('burst')
        else:
            interface_rate = burst = None
        mac = interface.findall('mac')[0].get('address')
        return cls(controller, name, bridge, mac, interface_rate=interface_rate, burst=burst)


    def to_xml(self):
        Interfacexml = self.controller.get_template('interface.xml').render(
            macaddress=self.mac, bridge=self.bridge.name, qos=self.qos, rate=self.interface_rate, burst=self.burst, name=self.name
        )
        return Interfacexml
