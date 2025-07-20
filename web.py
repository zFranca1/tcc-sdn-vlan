# import required libraries
from pox.lib.bottle import Bottle, response
from pox.core import core
from pox.flatfile_record.switch_aggports_ffrecord import get_file_path
import pox.openflow.libopenflow_01 as of
import pox.lib.util
import threading
import json
import time
import os
import ast

# initialize global variables
app = Bottle()
log = core.getLogger()
stats = None
port = long(38663)

# rest functions
@app.hook("after_request")
def enable_cors ():
    """
    Callback function to allow Cross-Origin Resource Sharing (CORS) for the
    content returned by all of the URL.
    
    Do not use the wildcard '*' for Access-Control-Allow-Origin in production.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "PUT, GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token"

@app.route("/web/jsonrest/of/controller/info")
def get_controller_information ():
    """
    Returns information about the controller. This includes:
     - Listen address (IP and port)
    
    :return: Information about the controller
    :rtype: JSONObject
    :except BaseException: If any error occurs returns an empty object
    """
    try:
        # get and verify module
        data = {}
        of = core.components.get("of_01")
        if of == None:
            log.error("Error getting module pox.openflow.of_01")
            return json.dumps(data)
        # build and return json data
        data = {
                "listenAddress": "*" if (of.address == "0.0.0.0") else of.address,
                "listenPort": of.port
                }
        return json.dumps(data)
    except BaseException, e:
        log.error(e.message)
        data = {}
        return json.dumps(data)

@app.route("/web/jsonrest/discovery/links")
def get_discovered_links ():
    """
    Returns a list of all inter-switch discovered links (note that these are
    only for switches connected to the controller). This includes:
     - Data layer source/destination
     - Port source/destination
    
    Requires to launch next modules:
     - :mod:`pox.openflow.discovery`
    
    :return: List of all inter-switch discovered links
    :rtype: JSONArray
    :except BaseException: If any error occurs returns an empty list
    """
    try:
        # get and verify module
        dataArray = []
        discovery = core.components.get("openflow_discovery")
        if discovery == None:
            log.error("Error getting module pox.openflow.discovery")
            return json.dumps(dataArray)
        # build and return json data
        links = discovery.adjacency
        for link in links.keys():
            data = {
                    "dataLayerSource": dpidToStr(link.dpid1),
                    "portSource": link.port1,
                    "dataLayerDestination": dpidToStr(link.dpid2),
                    "portDestination": link.port2
                    }
            dataArray.append(data)
        return json.dumps(dataArray)
    except BaseException, e:
        log.error(e.message)
        dataArray = []
        return json.dumps(dataArray)

@app.route("/web/jsonrest/of/switches")
def get_switches ():
    """
    Returns a list of all switches connected to the controller. This includes:
     - String DPID in format XX:XX:XX:XX:XX:XX:XX:XX
     - Remote address (IP and port)
     - Connection time
    
    :return: List of all switches connected to the controller
    :rtype: JSONArray
    :except BaseException: If any error occurs returns an empty list
    """
    try:
        # get and verify module
        dataArray = []
        openflow = core.components.get("openflow")
        if openflow == None:
            log.error("Error getting module pox.openflow")
            return json.dumps(dataArray)
        # build and return json data
        connections = openflow._connections
        fakePort = port
        for connKey in connections.keys():
            fakePort += 1
            connection = connections.get(connKey)
            switch_dpid = dpidToStr(connection.dpid)
            data = {
                    "dpid": switch_dpid,
                    "remoteIp": "192.168.56.2",
                    "remotePort": fakePort,
                    "connectedSince": connection.connect_time * 1000,
                    }
            dataArray.append(data)
        return json.dumps(dataArray)
    except BaseException, e:
        log.error(e.message)
        dataArray = []
        return json.dumps(dataArray)

@app.route("/web/jsonrest/of/switch/<switch_dpid>/aggregate")
def get_switch_aggregate (switch_dpid):
    """
    Returns per switch aggregate stats. This includes:
     - Bytes
     - Flows
     - Packets
    
    :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
    :type switch_dpid: str
    :return: Switch aggregate stats
    :rtype: JSONObject
    :except BaseException: If any error occurs returns an empty object
    """
    try:
        # build openflow message
        bodyMsg = of.ofp_aggregate_stats_request()
        bodyMsg.match = of.ofp_match()
        bodyMsg.table_id = of.TABLE_ALL
        bodyMsg.out_port = of.OFPP_NONE
        msg = of.ofp_stats_request(body = bodyMsg)
        msg.type = of.OFPST_AGGREGATE
        # get and verify stats
        data = {}
        aggStats = get_switch_stats(switch_dpid, msg, "aggregate flows")
        if aggStats == None:
            log.error("Error getting aggregate stats")
            return json.dumps(data)
        # build and return json data
        data = {
                "bytes": aggStats.byte_count,
                "flows": aggStats.flow_count,
                "packets": aggStats.packet_count
                }
        return json.dumps(data)
    except BaseException, e:
        log.error(e.message)
        data = {}
        return json.dumps(data)

@app.route("/web/jsonrest/of/switch/<switch_dpid>/desc")
def get_switch_description (switch_dpid):
    """
    Returns per switch a description. This includes:
     - Serial number
     - Manufacturer
     - Hardware
     - Software
     - Datapath
    
    :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
    :type switch_dpid: str
    :return: Switch description
    :rtype: JSONObject
    :except BaseException: If any error occurs returns an empty object
    """
    try:
        # build openflow message
        msg = of.ofp_stats_request()
        msg.type = of.OFPST_DESC
        # get and verify stats
        data = {}
        descStats = get_switch_stats(switch_dpid, msg, "description")
        if descStats == None:
            log.error("Error getting description stats")
            return json.dumps(data)
        # build and return json data
        data = {
                "serialNumber": descStats.serial_num,
                "manufacturer": descStats.mfr_desc,
                "hardware": descStats.hw_desc,
                "software": descStats.sw_desc,
                "datapath": descStats.dp_desc
                }
        return json.dumps(data)
    except BaseException, e:
        log.error(e.message)
        data = {}
        return json.dumps(data)


@app.route("/web/jsonrest/host_tracker/devices")
def get_tracked_devices ():
    """
    Returns a list of all hosts tracked by the controller. This includes:
     - Data layer address
     - Network addresses
     - Attachment point (switch DPID and port)
     - Last time seen
    
    Requires to launch next modules:
     - :mod:`pox.openflow.discovery`
     - :mod:`pox.host_tracker`
    
    :return: List of all hosts tracked by the controller
    :rtype: JSONArray
    :except BaseException: If any error occurs returns an empty list
    """
    try:
        # get and verify module
        dataArray = []
        host_tracker = core.components.get("host_tracker")
        if host_tracker == None:
            log.error("Error getting module pox.host_tracker")
            return json.dumps(dataArray)
        # build and return json data
        devices = host_tracker.entryByMAC
        for deviceKey in devices.keys():
            device = devices.get(deviceKey)
            networkAddresses = ""
            for ip in device.ipAddrs:
                if len(networkAddresses) > 0:
                    networkAddresses += " "
                networkAddresses += str(ip)
            data = {
                    "dataLayerAddress": str(device.macaddr),
                    "networkAddresses": networkAddresses,
                    "lastSeen": device.lastTimeSeen * 1000,
                    "switch_dpid": dpidToStr(device.dpid),
                    "port": device.port
                    }
            dataArray.append(data)
        return json.dumps(dataArray)
    except BaseException, e:
        log.error(e.message)
        dataArray = []
        return json.dumps(dataArray)


@app.route("/web/jsonrest/of/switch/<switch_dpid>/flows")
def get_switch_flows (switch_dpid):
    """
    Returns per switch a list of all flow stats. This includes:
     - Input port
     - Data layer source/destination
     - Network source/destination
     - Transport source/destination
     - Wildcards
     - Bytes
     - Packets
     - Time
     - Idle timeout
     - Hard timeout
     - Cookies
     - Output ports
    
    :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
    :type switch_dpid: str
    :return: List of all flow stats from the requested switch
    :rtype: JSONArray
    :except BaseException: If any error occurs returns an empty list
    """
    try:
        # build openflow message
        bodyMsg = of.ofp_flow_stats_request()
        bodyMsg.match = of.ofp_match()
        bodyMsg.table_id = of.TABLE_ALL
        bodyMsg.out_port = of.OFPP_NONE
        msg = of.ofp_stats_request(body = bodyMsg)
        msg.type = of.OFPST_FLOW
        # get and verify stats
        dataArray = []
        stats = get_switch_stats(switch_dpid, msg, "flows")
        if stats == None:
            log.error("Error getting flow stats")
            return json.dumps(dataArray)
        # build and return json data
        for flowStats in stats:
            outports = ""
            for action in flowStats.actions:
                if isinstance(action, of.ofp_action_output):
                    if len(outports) > 0:
                        outports += " "
                    outports += str(action.port)
            # Long format
            data = {
                    "inPort": flowStats.match._in_port,
                    "dataLayerSource": str(flowStats.match._dl_src),
                    "dataLayerDestination": str(flowStats.match._dl_dst),
                    "dataLayerType": flowStats.match._dl_type,
                    "networkSource": str(flowStats.match._nw_src),
                    "networkDestination": str(flowStats.match._nw_dst),
                    "networkProtocol": flowStats.match._nw_proto,
                    "transportSource": flowStats.match._tp_src,
                    "transportDestination": flowStats.match._tp_dst,
                    "wildcards": flowStats.match.wildcards,
                    "bytes": flowStats.byte_count,
                    "packets": flowStats.packet_count,
                    "time": float(flowStats.duration_sec) + (float(flowStats.duration_nsec) / float(1000000000)),
                    "idleTimeout": flowStats.idle_timeout,
                    "hardTimeout": flowStats.hard_timeout,
                    "cookie": flowStats.cookie,
                    "outports": outports,
                    "vlanId": flowStats.match._dl_vlan
                    }
            dataArray.append(data)
        return json.dumps(dataArray)
    except BaseException, e:
        log.error(e.message)
        dataArray = []
        return json.dumps(dataArray)

        @app.route("/web/jsonrest/of/switch/<switch_dpid>/flow")
        def get_switch_flows_by_switch(switch_dpid):
            """
            Returns per switch a list of flow stats filtered by switch DPID. This includes:
             - Input port
             - Data layer source/destination
             - Network source/destination
             - Transport source/destination
             - Wildcards
             - Bytes
             - Packets
             - Time
             - Idle timeout
             - Hard timeout
             - Cookies
             - Output ports
            
            :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
            :type switch_dpid: str
            :return: List of flow stats from the requested switch filtered by switch DPID
            :rtype: JSONArray
            :except BaseException: If any error occurs returns an empty list
            """
            try:
            # build openflow message
            bodyMsg = of.ofp_flow_stats_request()
            bodyMsg.match = of.ofp_match()
            bodyMsg.table_id = of.TABLE_ALL
            bodyMsg.out_port = of.OFPP_NONE
            msg = of.ofp_stats_request(body=bodyMsg)
            msg.type = of.OFPST_FLOW
            # get and verify stats
            dataArray = []
            stats = get_switch_stats(switch_dpid, msg, "flows")
            if stats == None:
                log.error("Error getting flow stats")
                return json.dumps(dataArray)
            # build and return json data
            for flowStats in stats:
                outports = ""
                for action in flowStats.actions:
                if isinstance(action, of.ofp_action_output):
                    if len(outports) > 0:
                    outports += " "
                    outports += str(action.port)
                # Long format
                data = {
                "inPort": flowStats.match._in_port,
                "dataLayerSource": str(flowStats.match._dl_src),
                "dataLayerDestination": str(flowStats.match._dl_dst),
                "dataLayerType": flowStats.match._dl_type,
                "networkSource": str(flowStats.match._nw_src),
                "networkDestination": str(flowStats.match._nw_dst),
                "networkProtocol": flowStats.match._nw_proto,
                "transportSource": flowStats.match._tp_src,
                "transportDestination": flowStats.match._tp_dst,
                "wildcards": flowStats.match.wildcards,
                "bytes": flowStats.byte_count,
                "packets": flowStats.packet_count,
                "time": float(flowStats.duration_sec) + (float(flowStats.duration_nsec) / float(1000000000)),
                "idleTimeout": flowStats.idle_timeout,
                "hardTimeout": flowStats.hard_timeout,
                "cookie": flowStats.cookie,
                "outports": outports,
                "vlanId": flowStats.match._dl_vlan
                }
                dataArray.append(data)
            return json.dumps(dataArray)
            except BaseException as e:
            log.error(str(e))
            dataArray = []
            return json.dumps(dataArray)

@app.route("/web/jsonrest/of/switch/<switch_dpid>/vlan")
def get_switch_vlans(switch_dpid):
    """
    Returns per switch VLAN information. This includes:
     - VLAN ID
     - VLAN name
    
    :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
    :type switch_dpid: str
    :return: Switch VLAN information
    :rtype: JSONArray
    :except BaseException: If any error occurs returns an empty list
    """
    try:
        # get and verify module
        dataArray = []
        openflow = core.components.get("openflow")
        if openflow == None:
            log.error("Error getting module pox.openflow")
            return json.dumps(dataArray)
        # build and return json data
        connections = openflow._connections
        for connKey in connections.keys():
            connection = connections.get(connKey)
            if dpidToStr(connection.dpid) == switch_dpid:
                vlans = connection.features.ports[0].name.split(",")
                for vlan in vlans:
                    data = {
                        "vlanId": vlan.split(":")[0],
                        "vlanName": vlan.split(":")[1]
                    }
                    dataArray.append(data)
                break
        return json.dumps(dataArray)
    except BaseException as e:
        log.error(str(e))
        dataArray = []
        return json.dumps(dataArray)


# event handler functions
def handle_AggregateFlowStatsReceived (event):
    """
    Handles aggregate flow stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("AggregateFlowStatsReceived")

def handle_DescStatsReceived (event):
    """
    Handles description stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("SwitchDescReceived")

def handle_FlowStatsReceived (event):
    """
    Handles flow stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("FlowStatsReceived")

def handle_PortStatsReceived (event):
    """
    Handles port stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("PortStatsReceived")

def handle_QueueStatsReceived (event):
    """
    Handles queue stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("QueueStatsReceived")

def handle_TableStatsReceived (event):
    """
    Handles table stats event.
    
    :param event: Event received to handle.
    """
    global stats
    stats = event.stats
    log.debug("TableStatsReceived")

# helper functions
def get_switch_stats (switch_dpid, msg, statsType):
    """
    Returns per switch and per type stats.
    
    :param switch_dpid: Switch DPID to request in format XX:XX:XX:XX:XX:XX:XX:XX
    :type switch_dpid: str
    :param msg: Message to send to the requested switch
    :type msg: str
    :param statsType: Identifies the type of stats requested
    :type statsType: str
    :return: Switch list of requested stats
    :rtype: dict or list
    :except BaseException: If any error occurs returns None
    """
    try:
        # check parameters
        global stats
        stats = None
        dpid = strToDPID(switch_dpid)
        # send openflow message
        core.openflow.sendToDPID(dpid, msg.pack())
        # wait for response to return stats
        initialTime = time.time()
        while stats == None:
            if (time.time() - initialTime) > 15:
                log.error("Timeout failure retrieving " + statsType + " stats")
                break
        return stats
    except BaseException, e:
        log.error("Failure retrieving " + statsType + " stats")
        log.error(e.message)
        return None

def dpidToStr (dpid):
    """
    Converts DPID from numeric format to format XX:XX:XX:XX:XX:XX:XX:XX.
    
    :param dpid: DPID in numeric format to convert
    :type dpid: int
    :return: DPID in format XX:XX:XX:XX:XX:XX:XX:XX
    :rtype: str
    """
    dpidStr = pox.lib.util.dpidToStr(dpid)
    dpidStr = dpidStr.replace("-", ":")
    dpidStr = "00:00:" + dpidStr
    return dpidStr

def strToDPID (dpidStr):
    """
    Converts DPID from format XX:XX:XX:XX:XX:XX:XX:XX in numeric format.
    
    :param dpidStr: DPID in format XX:XX:XX:XX:XX:XX:XX:XX to convert
    :type dpidStr: str
    :return: DPID in numeric format
    :rtype: int
    """
    dpidStr = dpidStr[6:]
    dpidStr = dpidStr.replace(":", "-")
    dpid = pox.lib.util.strToDPID(dpidStr)
    return dpid

# launch function
def launch (host = None, port = None):
    """
    Runs JSON REST and its required modules.
    
    :param host: Server address to bind to. Pass '0.0.0.0' to listens on all 
                 interfaces including the external one (default: 127.0.0.1).
    :type host: str
    :param port: Server port to bind to. Values below 1024 require root
                 privileges (default: 8080).
    :type port: str
    """
    # add listeners
    core.openflow.addListenerByName("AggregateFlowStatsReceived", handle_AggregateFlowStatsReceived)
    core.openflow.addListenerByName("SwitchDescReceived", handle_DescStatsReceived)
    core.openflow.addListenerByName("FlowStatsReceived", handle_FlowStatsReceived)
    core.openflow.addListenerByName("PortStatsReceived", handle_PortStatsReceived)
    core.openflow.addListenerByName("QueueStatsReceived", handle_QueueStatsReceived)
    core.openflow.addListenerByName("TableStatsReceived", handle_TableStatsReceived)

    # thread function
    def run():
        """
        Execute the Bottle server.
        """
        try:
            kwargs = {"host" : host, "port" : int(port)}
            app.run(**kwargs)
        except BaseException, e:
            log.error(e.message)
    # create and start thread
    thread = threading.Thread(target = run)
    thread.daemon = True
    thread.start()