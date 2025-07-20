from pox.core import core
import pox.openflow.libopenflow_01 as of

log = core.getLogger()

class FlowTableSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}

    def _handle_ConnectionUp(self, event):
        log.info("Switch %s conectado.", event.connection.dpid)

    def _handle_PacketIn(self, event):
        packet = event.parsed
        dpid = event.connection.dpid
        in_port = event.port

        # Extraindo informações do pacote
        src_mac = packet.src
        dst_mac = packet.dst
        src_ip = None
        dst_ip = None
        vlan_id = None
        protocol = None

        if packet.find('ipv4'):
            src_ip = packet.find('ipv4').srcip
            dst_ip = packet.find('ipv4').dstip
            protocol = packet.find('ipv4').protocol

        vlan_header = packet.find('vlan')
        if vlan_header:
            vlan_id = vlan_header.id

        # Exibindo as informações
        log.info("Switch %s received packet:", dpid)
        log.info("  Source MAC: %s", src_mac)
        log.info("  Destination MAC: %s", dst_mac)
        if src_ip and dst_ip:
            log.info("  Origem IP: %s", src_ip)
            log.info("  Destino IP: %s", dst_ip)
        if vlan_id is not None:
            log.info("  VLAN ID: %s", vlan_id) 

        # Verificando se o pacote é TCP ou UDP
        if protocol == 6:  # 6 é o valor numérico para o protocolo TCP
            log.info("É um pacote TCP")
        elif protocol == 17:  # 17 é o valor numérico para o protocolo UDP
            log.info("É um pacote UDP")
        else:
            log.info("Não é um pacote TCP nem UDP, Ignorando.")

        # Encaminhando o pacote apenas se houver uma entrada na tabela de encaminhamento
        if dst_mac in self.mac_to_port:
            out_port = self.mac_to_port[dst_mac]
            log.info("Forwarding packet from port %d to port %d on switch %s.", in_port, out_port, dpid)
            msg = of.ofp_flow_mod()
            msg.match = of.ofp_match.from_packet(packet, in_port)
            msg.actions.append(of.ofp_action_output(port=out_port))
            event.connection.send(msg) 

def launch():
    core.registerNew(FlowTableSwitch)

