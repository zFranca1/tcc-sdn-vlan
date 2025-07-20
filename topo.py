from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.link import TCLink

class VLANTopo(Topo):
    def build(self):
        switch = self.addSwitch('s1')
        h1 = self.addHost('h1', ip='10.0.0.1/24')
        h2 = self.addHost('h2', ip='10.0.0.2/24')
        h3 = self.addHost('h3', ip='10.0.0.3/24')
        h4 = self.addHost('h4', ip='10.0.0.4/24')
        self.addLink(h1, switch, port2=1)
        self.addLink(h2, switch, port2=2)
        self.addLink(h3, switch, port2=3)
        self.addLink(h4, switch, port2=4)

def run():
    topo = VLANTopo()
    net = Mininet(topo=topo, controller=RemoteController, link=TCLink)
    net.start()

    # Configurar VLANs nas interfaces do switch
    net['s1'].cmd('ovs-vsctl set port s1-eth1 tag=10')
    net['s1'].cmd('ovs-vsctl set port s1-eth2 tag=10')
    net['s1'].cmd('ovs-vsctl set port s1-eth3 tag=20')
    net['s1'].cmd('ovs-vsctl set port s1-eth4 tag=20')

    CLI(net)
    net.stop()

if __name__ == '__main__':
    run()

