from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class FlowTableSwitch(object):

    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}
        self.flows = set()  # Utilizaremos um conjunto para armazenar pares únicos de IP de origem e destino

    def _handle_ConnectionUp(self, event):
        log.info("Switch %s conectado.", event.connection.dpid)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        dpid = event.connection.dpid
        in_port = event.port

        # Extraindo informações do pacote
        src_ip = None
        dst_ip = None
        protocol = None
        src_port = None
        dst_port = None

        if packet.find('ipv4'):
            src_ip = packet.find('ipv4').srcip
            dst_ip = packet.find('ipv4').dstip

        if packet.find('tcp'):
            protocol = 'TCP'
            src_port = packet.find('tcp').srcport
            dst_port = packet.find('tcp').dstport
        elif packet.find('udp'):
            protocol = 'UDP'
            src_port = packet.find('udp').srcport
            dst_port = packet.find('udp').dstport

        # Identificando o fluxo com base no par de endereços IP de origem e destino e no protocolo
        flow_key = (src_ip, dst_ip, protocol)

        # Verificando se é um novo fluxo
        if flow_key not in self.flows:
            self.flows.add(flow_key)
            if protocol:
                log.info("Novo fluxo identificado ({}):".format(protocol))
            else:
                log.info("Novo fluxo identificado:")
            log.info("Origem IP: %s, Destino IP: %s, Protocolo: %s", src_ip, dst_ip, protocol)
        else:
            if protocol:
                log.info("Fluxo {} já conhecido:".format(protocol))
            else:
                log.info("Fluxo já conhecido:")
            log.info("Origem IP: %s, Destino IP: %s, Protocolo: %s", src_ip, dst_ip, protocol)

        # Encaminhamento do pacote
        if packet.dst in self.mac_to_port:
            out_port = self.mac_to_port[packet.dst]
            log.info("Encaminhando o pacote da porta %d para a porta %d no switch %s.", in_port, out_port, dpid)
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, in_port)
            msg.actions.append(of.ofp_action_output(port=out_port))
            event.connection.send(msg)

def launch():
    core.registerNew(FlowTableSwitch)
