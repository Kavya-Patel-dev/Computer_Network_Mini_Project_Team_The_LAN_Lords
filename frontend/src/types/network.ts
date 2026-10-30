export type NodeType =
  | 'router'
  | 'host'
  | 'pc'
  | 'server'
  // Cisco Packet Tracer Routers
  | 'cisco_2911'
  | 'cisco_2901'
  | 'cisco_1941'
  | 'cisco_4321'
  | 'cisco_1841'
  | 'cisco_2811'
  | 'cisco_819'
  | 'cisco_829'
  | 'cisco_2620xm'
  | 'cisco_4331'
  | 'cisco_4351'
  | 'cisco_4451'
  | 'router_pt'
  // Cisco Packet Tracer Switches
  | 'catalyst_2960'
  | 'catalyst_3560'
  | 'catalyst_3650'
  | 'catalyst_2950'
  | 'catalyst_2960x'
  | 'catalyst_3750'
  | 'catalyst_3850'
  | 'catalyst_9200'
  | 'multilayer_switch_pt'
  | 'bridge_pt'
  | 'switch_pt'
  // Hubs & Repeaters
  | 'hub_pt'
  | 'repeater_pt'
  | 'coaxial_splitter'
  // Wireless
  | 'wrt300n'
  | 'ap_pt'
  | 'cell_tower'
  | 'wlc_pt'
  | 'home_gateway'
  // Security
  | 'asa_5506'
  | 'asa_5505'
  | 'asa_5508'
  | 'ips_pt'
  // WAN Emulation
  | 'cloud_pt'
  | 'dsl_modem'
  | 'cable_modem'
  | 'dslam_pt'
  // End Devices
  | 'laptop'
  | 'ip_phone'
  | 'printer'
  | 'tablet'
  | 'smartphone'
  | 'iot'
  | 'analog_phone'
  | 'tv_pt'
  | 'webcam_pt'
  | 'wireless_end_device'
  | 'motion_sensor'
  | 'temperature_sensor'
  | 'smart_light'
  | 'smart_door'
  | 'fan_pt'
  | 'sprinkler_pt'
  | 'garage_door_pt'
  | 'registration_server'
  | 'custom_device';

export type CiscoDeviceCategory =
  | 'routers'
  | 'switches'
  | 'hubs'
  | 'wireless'
  | 'security'
  | 'wan'
  | 'end_devices';

export type CableType =
  | 'copper_straight'
  | 'copper_cross'
  | 'fiber'
  | 'serial'
  | 'console'
  | 'phone'
  | 'coaxial'
  | 'usb'
  | 'octal'
  | 'wireless'
  | 'auto';

export interface DeviceInterface {
  id: string;
  name: string;
  speedMbps: number;
  ipAddress?: string;
  subnetMask?: string;
  macAddress?: string;
  isUp: boolean;
  connectedTo?: {
    nodeId: string;
    portName: string;
    linkId: string;
  };
}

export interface NetworkNode {
  id: string;
  type: NodeType;
  label: string;
  x?: number;
  y?: number;
  category?: CiscoDeviceCategory;
  model?: string;
  /** User-selected abstraction used by the routing simulator for custom Packet Tracer models. */
  simulationRole?: 'router' | 'host';
  department?: string;
  ip?: string;
  subnet?: string;
  gateway?: string;
  interfaces?: DeviceInterface[];
}

export interface NetworkLink {
  id: string;
  src: string;
  dst: string;
  bandwidth_mbps: number;
  latency_ms: number;
  loss_percent: number;
  status?: 'active' | 'congested' | 'failed';
  cableType?: CableType;
  /** Management cables can be drawn for documentation but do not carry simulated traffic. */
  simulationIncluded?: boolean;
  srcPort?: string;
  dstPort?: string;
}

export interface Topology {
  id: string;
  name: string;
  nodes: NetworkNode[];
  links: NetworkLink[];
}

// Helper to determine if a node performs L3 routing/forwarding in simulation
export function isRoutingNode(type: NodeType, simulationRole?: NetworkNode['simulationRole']): boolean {
  if (simulationRole) return simulationRole === 'router';
  return [
    'router',
    'cisco_2911',
    'cisco_2901',
    'cisco_1941',
    'cisco_4321',
    'cisco_1841',
    'cisco_2811',
    'cisco_819',
    'cisco_829',
    'cisco_2620xm',
    'cisco_4331',
    'cisco_4351',
    'cisco_4451',
    'router_pt',
    'catalyst_2960',
    'catalyst_2950',
    'catalyst_2960x',
    'catalyst_3560',
    'catalyst_3650',
    'catalyst_3750',
    'catalyst_3850',
    'catalyst_9200',
    'multilayer_switch_pt',
    'switch_pt',
    'bridge_pt',
    'hub_pt',
    'repeater_pt',
    'coaxial_splitter',
    'ap_pt',
    'wlc_pt',
    'cell_tower',
    'asa_5506',
    'asa_5505',
    'asa_5508',
    'ips_pt',
    'wrt300n',
    'home_gateway',
    'cloud_pt',
    'dsl_modem',
    'cable_modem',
    'dslam_pt',
  ].includes(type);
}

// Helper to determine if a node is an end device/host
export function isHostNode(type: NodeType, simulationRole?: NetworkNode['simulationRole']): boolean {
  if (simulationRole) return simulationRole === 'host';
  return [
    'pc',
    'server',
    'laptop',
    'ip_phone',
    'printer',
    'tablet',
    'smartphone',
    'iot',
    'analog_phone',
    'tv_pt',
    'webcam_pt',
    'wireless_end_device',
    'motion_sensor',
    'temperature_sensor',
    'smart_light',
    'smart_door',
    'fan_pt',
    'sprinkler_pt',
    'garage_door_pt',
    'registration_server',
    'host',
  ].includes(type);
}

export type TrafficClass = 'real_time' | 'streaming' | 'bulk' | 'background';

export interface TrafficFlow {
  id: string;
  src: string;
  dst: string;
  demand_mbps: number;
  class: TrafficClass;
}

export type ScenarioType =
  | 'normal'
  | 'link_failure'
  | 'router_failure'
  | 'traffic_spike'
  | 'bandwidth_drop';

export interface AnalysisReportData {
  singlePointsOfFailure: {
    routers: string[];
    links: string[];
  };
  bottlenecks: Array<{
    linkId: string;
    src: string;
    dst: string;
    loadSharePct: number;
    capacityMbps: number;
  }>;
  pathDiversityScore: number; // e.g. 78%
  diversityExplanation: string;
  suggestedImprovements: Array<{
    id: string;
    description: string;
    benefit: string;
    action: string;
  }>;
}
