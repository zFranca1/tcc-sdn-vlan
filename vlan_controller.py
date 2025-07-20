from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str

log = core.getLogger()

class VLANController(object):
    def __init__(self):
        core.openflow.addListeners(self)
        self.mac_to_port = {}
        self.vlan_to_ports = {10: [1, 2], 20: [3, 4]}

    def _handle_ConnectionUp(self, event):
        log.info("Switch %s has come up.", dpid_to_str(event.dpid))
        
        # Configurar VLANs
        for vlan_id, ports in self.vlan_to_ports.items():
            self.setup_vlan(event, vlan_id, ports)

    def setup_vlan(self, event, vlan_id, ports):
        for in_port in ports:
            # Regra para tratar pacotes dentro da VLAN
            match = of.ofp_match(in_port=in_port, dl_vlan=vlan_id)
            actions = [of.ofp_action_output(port=of.OFPP_NORMAL)]
            msg = of.ofp_flow_mod(command=of.OFPFC_ADD, priority=100, match=match, actions=actions)
            event.connection.send(msg)

        log.info(f"Configured VLAN {vlan_id} on switch {dpid_to_str(event.dpid)} for ports {ports}")

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet.parsed:
            log.warning("Ignoring incomplete packet")
            return

        in_port = event.port
        dpid = event.dpid

        # Determinar a VLAN do pacote
        vlan_id = None
        for v, ports in self.vlan_to_ports.items():
            if in_port in ports:
                vlan_id = v
                break

        if vlan_id is None:
            log.warning(f"Packet from unknown VLAN on port {in_port}")
            return

        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][packet.src] = in_port

        if packet.dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][packet.dst]
        else:
            out_port = of.OFPP_FLOOD

        # Verificar se a porta de saída está na mesma VLAN
        if out_port != of.OFPP_FLOOD and out_port not in self.vlan_to_ports[vlan_id]:
            log.warning(f"Blocking inter-VLAN traffic from port {in_port} to {out_port}")
            return

        actions = [of.ofp_action_output(port=out_port)]

        if out_port == of.OFPP_FLOOD:
            # Se for flood, apenas enviar para portas da mesma VLAN
            actions = [of.ofp_action_output(port=p) for p in self.vlan_to_ports[vlan_id] if p != in_port]

        msg = of.ofp_packet_out()
        msg.actions = actions
        msg.data = event.ofp
        msg.in_port = in_port
        event.connection.send(msg)

        if out_port != of.OFPP_FLOOD:
            match = of.ofp_match.from_packet(packet, in_port)
            match.dl_vlan = vlan_id
            self.add_flow(event, match, actions)

    def add_flow(self, event, match, actions):
        msg = of.ofp_flow_mod(
            command=of.OFPFC_ADD,
            idle_timeout=10,
            hard_timeout=30,
            buffer_id=event.ofp.buffer_id,
            actions=actions,
            match=match)
        event.connection.send(msg)

def launch():
    core.registerNew(VLANController)
