import { NodeType, CiscoDeviceCategory, CableType, DeviceInterface, NetworkNode } from '../types/network';

export interface CiscoHardwareItem {
  type: NodeType;
  name: string;
  shortName: string;
  category: CiscoDeviceCategory;
  badge: string;
  description: string;
  defaultPorts: string[];
  defaultBandwidth: number;
  defaultLatency: number;
  iconShape: 'router' | 'switch' | 'l3switch' | 'hub' | 'wireless' | 'firewall' | 'cloud' | 'pc' | 'laptop' | 'server' | 'phone' | 'printer' | 'tablet' | 'smartphone' | 'iot';
}

export interface CableDefinition {
  type: CableType;
  name: string;
  color: string;
  strokeDash?: string;
  defaultSpeed: number;
  description: string;
  recommendedUse: string;
  simulationSupported?: boolean;
}

export const CISCO_HARDWARE_CATALOG: CiscoHardwareItem[] = [
  // ==================== ROUTERS ====================
  {
    type: 'cisco_2911',
    name: 'Cisco 2911 Integrated Services Router',
    shortName: '2911',
    category: 'routers',
    badge: 'ISR-G2',
    description: 'Modular enterprise router with 3 Gigabit Ethernet ports and 4 EHWIC slots for voice and WAN serial links.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1', 'GigabitEthernet0/2', 'Serial0/0/0', 'Serial0/0/1'],
    defaultBandwidth: 1000,
    defaultLatency: 2,
    iconShape: 'router',
  },
  {
    type: 'cisco_2901',
    name: 'Cisco 2901 Integrated Services Router',
    shortName: '2901',
    category: 'routers',
    badge: 'ISR-G2',
    description: 'Compact enterprise branch router with 2 Gigabit Ethernet ports and 4 high-speed WAN interface card slots.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1', 'Serial0/0/0', 'Serial0/0/1'],
    defaultBandwidth: 1000,
    defaultLatency: 2,
    iconShape: 'router',
  },
  {
    type: 'cisco_1941',
    name: 'Cisco 1941 Modular Router',
    shortName: '1941',
    category: 'routers',
    badge: 'ISR-G2',
    description: 'Secure data routing platform with 2 onboard GE ports and HWIC support for edge branch networks.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1', 'Serial0/1/0'],
    defaultBandwidth: 1000,
    defaultLatency: 2.5,
    iconShape: 'router',
  },
  {
    type: 'cisco_4321',
    name: 'Cisco 4321 Integrated Services Router',
    shortName: '4321',
    category: 'routers',
    badge: 'ISR 4000',
    description: 'Next-gen enterprise WAN ISR with multicore architecture, 50-100 Mbps aggregate throughput, and SFP combo ports.',
    defaultPorts: ['GigabitEthernet0/0/0', 'GigabitEthernet0/0/1', 'GigabitEthernet0/0/2'],
    defaultBandwidth: 1000,
    defaultLatency: 1.5,
    iconShape: 'router',
  },
  {
    type: 'cisco_1841',
    name: 'Cisco 1841 Modular Router',
    shortName: '1841',
    category: 'routers',
    badge: 'Classic ISR',
    description: 'Classic modular router featuring 2 FastEthernet interfaces and dual WIC expansion bays.',
    defaultPorts: ['FastEthernet0/0', 'FastEthernet0/1', 'Serial0/0/0'],
    defaultBandwidth: 100,
    defaultLatency: 4,
    iconShape: 'router',
  },
  {
    type: 'cisco_2811',
    name: 'Cisco 2811 Integrated Router',
    shortName: '2811',
    category: 'routers',
    badge: 'Classic ISR',
    description: 'Multi-service business router supporting high-density voice, serial, and dual FastEthernet routed interfaces.',
    defaultPorts: ['FastEthernet0/0', 'FastEthernet0/1', 'FastEthernet0/2', 'Serial0/0/0'],
    defaultBandwidth: 100,
    defaultLatency: 3.5,
    iconShape: 'router',
  },
  {
    type: 'router_pt',
    name: 'Router-PT Generic Modular Router',
    shortName: 'Router-PT',
    category: 'routers',
    badge: 'Generic',
    description: 'Packet Tracer generic modular router with empty expansion bays customizable for Ethernet, FastEthernet, and Serial.',
    defaultPorts: ['FastEthernet0/0', 'FastEthernet1/0', 'Serial2/0', 'Serial3/0'],
    defaultBandwidth: 100,
    defaultLatency: 3,
    iconShape: 'router',
  },
  {
    type: 'cisco_819', name: 'Cisco 819 Industrial Integrated Services Router', shortName: '819',
    category: 'routers', badge: 'ISR / LTE',
    description: 'Compact ruggedized branch router with Ethernet and cellular WAN interfaces.',
    defaultPorts: ['GigabitEthernet0', 'FastEthernet0', 'Cellular0'], defaultBandwidth: 1000, defaultLatency: 3, iconShape: 'router',
  },
  {
    type: 'cisco_829', name: 'Cisco 829 Industrial Router', shortName: '829',
    category: 'routers', badge: 'ISR / LTE',
    description: 'Industrial router model for remote sites and machine networks.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1', 'Cellular0'], defaultBandwidth: 1000, defaultLatency: 3, iconShape: 'router',
  },
  {
    type: 'cisco_2620xm', name: 'Cisco 2620XM Modular Router', shortName: '2620XM',
    category: 'routers', badge: 'Classic ISR',
    description: 'Legacy modular router for Ethernet and serial WAN labs.',
    defaultPorts: ['FastEthernet0/0', 'Serial0/0/0', 'Serial0/0/1'], defaultBandwidth: 100, defaultLatency: 4, iconShape: 'router',
  },
  {
    type: 'cisco_4331', name: 'Cisco 4331 Integrated Services Router', shortName: '4331',
    category: 'routers', badge: 'ISR 4000',
    description: 'Branch router with modular WAN connectivity and Gigabit interfaces.',
    defaultPorts: ['GigabitEthernet0/0/0', 'GigabitEthernet0/0/1', 'GigabitEthernet0/0/2'], defaultBandwidth: 1000, defaultLatency: 1.5, iconShape: 'router',
  },
  {
    type: 'cisco_4351', name: 'Cisco 4351 Integrated Services Router', shortName: '4351',
    category: 'routers', badge: 'ISR 4000',
    description: 'Higher-capacity modular branch router with multiple WAN and LAN interfaces.',
    defaultPorts: ['GigabitEthernet0/0/0', 'GigabitEthernet0/0/1', 'GigabitEthernet0/0/2'], defaultBandwidth: 1000, defaultLatency: 1.2, iconShape: 'router',
  },
  {
    type: 'cisco_4451', name: 'Cisco 4451-X Integrated Services Router', shortName: '4451-X',
    category: 'routers', badge: 'ISR 4000',
    description: 'Enterprise edge router model for larger branch and WAN designs.',
    defaultPorts: ['GigabitEthernet0/0/0', 'GigabitEthernet0/0/1', 'GigabitEthernet0/0/2'], defaultBandwidth: 1000, defaultLatency: 1, iconShape: 'router',
  },

  // ==================== SWITCHES ====================
  {
    type: 'catalyst_2960',
    name: 'Cisco Catalyst 2960-24TT Switch',
    shortName: '2960',
    category: 'switches',
    badge: 'Catalyst L2',
    description: 'Enterprise-class standalone Layer 2 switch with 24 10/100 ports and 2 10/100/1000TX uplinks.',
    defaultPorts: [
      'FastEthernet0/1', 'FastEthernet0/2', 'FastEthernet0/3', 'FastEthernet0/4',
      'FastEthernet0/5', 'FastEthernet0/6', 'FastEthernet0/7', 'FastEthernet0/8',
      'GigabitEthernet0/1', 'GigabitEthernet0/2'
    ],
    defaultBandwidth: 100,
    defaultLatency: 1,
    iconShape: 'switch',
  },
  {
    type: 'catalyst_3560',
    name: 'Cisco Catalyst 3560-24PS Multilayer Switch',
    shortName: '3560-24PS',
    category: 'switches',
    badge: 'L3 Multilayer',
    description: 'Layer 3 multilayer switch supporting IP routing (OSPF, EIGRP, RIP, static) with 24 10/100 PoE ports and 2 SFP uplinks.',
    defaultPorts: [
      'FastEthernet0/1', 'FastEthernet0/2', 'FastEthernet0/3', 'FastEthernet0/4',
      'GigabitEthernet0/1', 'GigabitEthernet0/2'
    ],
    defaultBandwidth: 1000,
    defaultLatency: 0.8,
    iconShape: 'l3switch',
  },
  {
    type: 'catalyst_3650',
    name: 'Cisco Catalyst 3650-24TS Multilayer Switch',
    shortName: '3650-24TS',
    category: 'switches',
    badge: 'L3 Stacking',
    description: 'Enterprise converged wired-wireless Layer 3 switch with 24 10/100/1000 Ethernet ports and 4 1G SFP uplinks.',
    defaultPorts: [
      'GigabitEthernet1/0/1', 'GigabitEthernet1/0/2', 'GigabitEthernet1/0/3', 'GigabitEthernet1/0/4',
      'GigabitEthernet1/1/1', 'GigabitEthernet1/1/2'
    ],
    defaultBandwidth: 1000,
    defaultLatency: 0.5,
    iconShape: 'l3switch',
  },
  {
    type: 'switch_pt',
    name: 'Switch-PT Generic Switch',
    shortName: 'Switch-PT',
    category: 'switches',
    badge: 'Generic',
    description: 'Packet Tracer generic modular Layer 2 switch with custom interface slot expansion.',
    defaultPorts: ['FastEthernet0/1', 'FastEthernet1/1', 'FastEthernet2/1', 'GigabitEthernet3/1'],
    defaultBandwidth: 100,
    defaultLatency: 1.2,
    iconShape: 'switch',
  },
  {
    type: 'catalyst_2950', name: 'Cisco Catalyst 2950-24 Switch', shortName: '2950-24',
    category: 'switches', badge: 'Catalyst L2',
    description: 'Legacy 24-port Fast Ethernet access switch for classic Packet Tracer labs.',
    defaultPorts: Array.from({ length: 24 }, (_, index) => `FastEthernet0/${index + 1}`), defaultBandwidth: 100, defaultLatency: 1.2, iconShape: 'switch',
  },
  {
    type: 'catalyst_2960x', name: 'Cisco Catalyst 2960-X 24-Port Switch', shortName: '2960-X',
    category: 'switches', badge: 'Catalyst L2',
    description: 'Access-layer switch with Fast Ethernet ports and Gigabit uplinks.',
    defaultPorts: [...Array.from({ length: 24 }, (_, index) => `GigabitEthernet0/${index + 1}`), 'TenGigabitEthernet0/1', 'TenGigabitEthernet0/2'], defaultBandwidth: 1000, defaultLatency: 0.9, iconShape: 'switch',
  },
  {
    type: 'catalyst_3750', name: 'Cisco Catalyst 3750 Multilayer Switch', shortName: '3750',
    category: 'switches', badge: 'Catalyst L3',
    description: 'Stackable multilayer switch used for routed campus distribution.',
    defaultPorts: [...Array.from({ length: 24 }, (_, index) => `FastEthernet1/0/${index + 1}`), 'GigabitEthernet1/0/1', 'GigabitEthernet1/0/2'], defaultBandwidth: 1000, defaultLatency: 0.8, iconShape: 'l3switch',
  },
  {
    type: 'catalyst_3850', name: 'Cisco Catalyst 3850 Multilayer Switch', shortName: '3850',
    category: 'switches', badge: 'Catalyst L3',
    description: 'Enterprise access and distribution switch with routed uplinks.',
    defaultPorts: [...Array.from({ length: 24 }, (_, index) => `GigabitEthernet1/0/${index + 1}`), 'TenGigabitEthernet1/1/1', 'TenGigabitEthernet1/1/2'], defaultBandwidth: 1000, defaultLatency: 0.6, iconShape: 'l3switch',
  },
  {
    type: 'catalyst_9200', name: 'Cisco Catalyst 9200 Switch', shortName: '9200',
    category: 'switches', badge: 'Catalyst L3',
    description: 'Modern campus access switch model with Gigabit Ethernet interfaces.',
    defaultPorts: [...Array.from({ length: 24 }, (_, index) => `GigabitEthernet1/0/${index + 1}`), 'TenGigabitEthernet1/1/1', 'TenGigabitEthernet1/1/2'], defaultBandwidth: 1000, defaultLatency: 0.5, iconShape: 'l3switch',
  },
  {
    type: 'multilayer_switch_pt', name: 'Multilayer Switch-PT', shortName: 'MLS-PT',
    category: 'switches', badge: 'Packet Tracer L3',
    description: 'Generic multilayer switch for simulated routed campus topologies.',
    defaultPorts: ['GigabitEthernet0/1', 'GigabitEthernet0/2', 'GigabitEthernet0/3', 'GigabitEthernet0/4'], defaultBandwidth: 1000, defaultLatency: 0.8, iconShape: 'l3switch',
  },
  {
    type: 'bridge_pt', name: 'Bridge-PT', shortName: 'Bridge-PT',
    category: 'switches', badge: 'Layer 2',
    description: 'Two-port Ethernet bridge model for small Layer 2 segments.',
    defaultPorts: ['Port0', 'Port1'], defaultBandwidth: 100, defaultLatency: 1.5, iconShape: 'switch',
  },

  // ==================== HUBS & REPEATERS ====================
  {
    type: 'hub_pt',
    name: 'Hub-PT Generic Multiport Repeater',
    shortName: 'Hub-PT',
    category: 'hubs',
    badge: 'Layer 1',
    description: 'Standard 6-port broadcast collision domain repeater hub for legacy Ethernet topologies.',
    defaultPorts: ['FastEthernet0', 'FastEthernet1', 'FastEthernet2', 'FastEthernet3', 'FastEthernet4', 'FastEthernet5'],
    defaultBandwidth: 100,
    defaultLatency: 2,
    iconShape: 'hub',
  },
  {
    type: 'repeater_pt',
    name: 'Repeater-PT 2-Port Signal Regenerator',
    shortName: 'Repeater-PT',
    category: 'hubs',
    badge: 'Layer 1',
    description: 'Two-port physical layer signal regeneration repeater to extend maximum copper segment distance.',
    defaultPorts: ['FastEthernet0', 'FastEthernet1'],
    defaultBandwidth: 100,
    defaultLatency: 1.5,
    iconShape: 'hub',
  },
  {
    type: 'coaxial_splitter',
    name: 'Coaxial Splitter-PT (3-Way)',
    shortName: 'Coax-Splitter',
    category: 'hubs',
    badge: 'RF Splitter',
    description: 'Passive broadband RF coaxial splitter dividing incoming CATV signal to multiple cable modems.',
    defaultPorts: ['Port0 (In)', 'Port1 (Out)', 'Port2 (Out)'],
    defaultBandwidth: 500,
    defaultLatency: 1,
    iconShape: 'hub',
  },

  // ==================== WIRELESS DEVICES ====================
  {
    type: 'wrt300n',
    name: 'Linksys WRT300N Wireless-N Router',
    shortName: 'WRT300N',
    category: 'wireless',
    badge: 'Wi-Fi N / NAT',
    description: 'Broadband SOHO wireless router with 4-port Gigabit switch, SPI firewall, and 802.11b/g/n dual antenna.',
    defaultPorts: ['Internet (WAN)', 'Ethernet1', 'Ethernet2', 'Ethernet3', 'Ethernet4', 'Wireless0'],
    defaultBandwidth: 300,
    defaultLatency: 3,
    iconShape: 'wireless',
  },
  {
    type: 'ap_pt',
    name: 'AccessPoint-PT Wireless Access Point',
    shortName: 'AP-PT',
    category: 'wireless',
    badge: '802.11ac',
    description: 'Standalone wireless access point bridging 802.11 Wi-Fi clients onto wired Ethernet backbone.',
    defaultPorts: ['Port0 (Ethernet)', 'Port1 (SSID)'],
    defaultBandwidth: 1000,
    defaultLatency: 2,
    iconShape: 'wireless',
  },
  {
    type: 'cell_tower',
    name: 'Cell Tower Base Station',
    shortName: 'Cell-Tower',
    category: 'wireless',
    badge: '4G/5G LTE',
    description: 'Cellular WAN base station transceiver providing wireless broadband to smartphones and cellular tablets.',
    defaultPorts: ['Coaxial0', '3G/4G Cell0'],
    defaultBandwidth: 500,
    defaultLatency: 15,
    iconShape: 'wireless',
  },
  {
    type: 'wlc_pt', name: 'Wireless LAN Controller-PT', shortName: 'WLC-PT',
    category: 'wireless', badge: 'Wireless Controller',
    description: 'Central controller model for managing access points in a wireless campus.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1'], defaultBandwidth: 1000, defaultLatency: 2, iconShape: 'wireless',
  },
  {
    type: 'home_gateway', name: 'Home Gateway-PT', shortName: 'Home-GW',
    category: 'wireless', badge: 'IoT Gateway',
    description: 'Small-office and smart-home gateway with Ethernet, Wi-Fi, and IoT connectivity.',
    defaultPorts: ['Internet', 'Ethernet1', 'Ethernet2', 'Wireless0'], defaultBandwidth: 300, defaultLatency: 3, iconShape: 'wireless',
  },

  // ==================== SECURITY DEVICES ====================
  {
    type: 'asa_5506',
    name: 'Cisco ASA 5506-X Adaptive Security Appliance',
    shortName: 'ASA 5506-X',
    category: 'security',
    badge: 'Firepower',
    description: 'Next-generation firewall with 8 routed Gigabit Ethernet ports, stateful inspection, and ACL rule enforcement.',
    defaultPorts: [
      'GigabitEthernet1/1 (Inside)', 'GigabitEthernet1/2 (Outside)', 'GigabitEthernet1/3 (DMZ)',
      'GigabitEthernet1/4', 'Management1/1'
    ],
    defaultBandwidth: 1000,
    defaultLatency: 2,
    iconShape: 'firewall',
  },
  {
    type: 'asa_5505', name: 'Cisco ASA 5505 Security Appliance', shortName: 'ASA-5505',
    category: 'security', badge: 'Firewall',
    description: 'Small-site firewall model with multiple Ethernet interfaces.',
    defaultPorts: ['Ethernet0/0', 'Ethernet0/1', 'Ethernet0/2', 'Ethernet0/3'], defaultBandwidth: 100, defaultLatency: 2.5, iconShape: 'firewall',
  },
  {
    type: 'asa_5508', name: 'Cisco ASA 5508-X Security Appliance', shortName: 'ASA-5508',
    category: 'security', badge: 'Firewall',
    description: 'Next-generation firewall model for routed enterprise security zones.',
    defaultPorts: ['GigabitEthernet1/1', 'GigabitEthernet1/2', 'GigabitEthernet1/3', 'GigabitEthernet1/4'], defaultBandwidth: 1000, defaultLatency: 1.8, iconShape: 'firewall',
  },
  {
    type: 'ips_pt', name: 'Intrusion Prevention System-PT', shortName: 'IPS-PT',
    category: 'security', badge: 'Security',
    description: 'Inline security inspection appliance model for network diagrams.',
    defaultPorts: ['GigabitEthernet0/0', 'GigabitEthernet0/1'], defaultBandwidth: 1000, defaultLatency: 2, iconShape: 'firewall',
  },

  // ==================== WAN EMULATION ====================
  {
    type: 'cloud_pt',
    name: 'Cloud-PT Multi-Access WAN Cloud',
    shortName: 'Cloud-PT',
    category: 'wan',
    badge: 'WAN / Frame-Relay',
    description: 'Multiprotocol WAN simulation cloud supporting Frame Relay, Cable Headend, DSL DSLAM, and Ethernet backhaul.',
    defaultPorts: ['Ethernet6', 'Ethernet7', 'Serial0', 'Serial1', 'Modem4', 'Modem5'],
    defaultBandwidth: 1000,
    defaultLatency: 18,
    iconShape: 'cloud',
  },
  {
    type: 'dsl_modem',
    name: 'DSL Modem-PT Broadband Transceiver',
    shortName: 'DSL-Modem',
    category: 'wan',
    badge: 'ADSL2+',
    description: 'Asymmetric Digital Subscriber Line modem with RJ-11 telephone line jack and RJ-45 Ethernet bridge.',
    defaultPorts: ['Port0 (RJ-11 Phone)', 'Port1 (FastEthernet)'],
    defaultBandwidth: 50,
    defaultLatency: 12,
    iconShape: 'cloud',
  },
  {
    type: 'cable_modem',
    name: 'Cable Modem-PT DOCSIS Broadband Modem',
    shortName: 'Cable-Modem',
    category: 'wan',
    badge: 'DOCSIS 3.0',
    description: 'Coaxial cable modem bridging hybrid fiber-coaxial cable WAN to internal Ethernet LAN routers.',
    defaultPorts: ['Port0 (Coaxial)', 'Port1 (FastEthernet)'],
    defaultBandwidth: 200,
    defaultLatency: 8,
    iconShape: 'cloud',
  },
  {
    type: 'dslam_pt', name: 'DSLAM-PT Broadband Access Multiplexer', shortName: 'DSLAM-PT',
    category: 'wan', badge: 'Provider Access',
    description: 'Provider-side DSL aggregation node for connecting modem access links to a WAN.',
    defaultPorts: ['Phone0', 'Phone1', 'Phone2', 'Phone3', 'Ethernet0'], defaultBandwidth: 1000, defaultLatency: 5, iconShape: 'cloud',
  },

  // ==================== END DEVICES ====================
  {
    type: 'pc',
    name: 'PC-PT Desktop Workstation',
    shortName: 'PC-PT',
    category: 'end_devices',
    badge: 'Desktop',
    description: 'Standard desktop client workstation with FastEthernet NIC, IP stack, terminal, and command prompt.',
    defaultPorts: ['FastEthernet0', 'RS 232'],
    defaultBandwidth: 100,
    defaultLatency: 1,
    iconShape: 'pc',
  },
  {
    type: 'laptop',
    name: 'Laptop-PT Mobile Workstation',
    shortName: 'Laptop-PT',
    category: 'end_devices',
    badge: 'Laptop',
    description: 'Portable laptop computer equipped with FastEthernet adapter and optional Wireless 802.11n card.',
    defaultPorts: ['FastEthernet0', 'Wireless0'],
    defaultBandwidth: 100,
    defaultLatency: 1,
    iconShape: 'laptop',
  },
  {
    type: 'server',
    name: 'Server-PT Multifunction Server',
    shortName: 'Server-PT',
    category: 'end_devices',
    badge: 'Web/DNS/DHCP',
    description: 'Enterprise server supporting HTTP, DHCP, DNS, TFTP, NTP, Email, and Syslog simulation daemons.',
    defaultPorts: ['FastEthernet0', 'GigabitEthernet0'],
    defaultBandwidth: 1000,
    defaultLatency: 1,
    iconShape: 'server',
  },
  {
    type: 'ip_phone',
    name: 'Cisco IP Phone 7960 VoIP Terminal',
    shortName: 'IP-Phone 7960',
    category: 'end_devices',
    badge: 'VoIP',
    description: 'Enterprise IP phone featuring built-in 2-port 10/100 Ethernet switch for PC passthrough and PoE.',
    defaultPorts: ['SW (Switch)', 'PC (Pass-through)'],
    defaultBandwidth: 100,
    defaultLatency: 1.5,
    iconShape: 'phone',
  },
  {
    type: 'printer',
    name: 'Printer-PT Network Laser Printer',
    shortName: 'Printer-PT',
    category: 'end_devices',
    badge: 'Network Print',
    description: 'Shared network departmental laser printer with FastEthernet network interface card.',
    defaultPorts: ['FastEthernet0'],
    defaultBandwidth: 100,
    defaultLatency: 2,
    iconShape: 'printer',
  },
  {
    type: 'tablet',
    name: 'Tablet-PC Wireless Tablet',
    shortName: 'Tablet-PC',
    category: 'end_devices',
    badge: 'Touch Wi-Fi',
    description: 'Wireless tablet device with 802.11ac Wi-Fi and 4G/LTE cellular mobile interfaces.',
    defaultPorts: ['Wireless0', 'Cellular0'],
    defaultBandwidth: 150,
    defaultLatency: 4,
    iconShape: 'tablet',
  },
  {
    type: 'smartphone',
    name: 'Smartphone Smart Mobile Device',
    shortName: 'Smartphone',
    category: 'end_devices',
    badge: 'Mobile 5G',
    description: 'Cellular and Wi-Fi enabled smartphone with web browser and push notification simulation.',
    defaultPorts: ['Wireless0', 'Cellular0'],
    defaultBandwidth: 100,
    defaultLatency: 5,
    iconShape: 'smartphone',
  },
  {
    type: 'iot',
    name: 'Generic IoT Device / Smart Sensor',
    shortName: 'IoT-Device',
    category: 'end_devices',
    badge: 'Smart Sensor',
    description: 'Internet-of-Things embedded microcontroller sensor sending periodic telemetry flows.',
    defaultPorts: ['FastEthernet0'],
    defaultBandwidth: 10,
    defaultLatency: 3,
    iconShape: 'iot',
  },
  {
    type: 'analog_phone', name: 'Analog Phone-PT', shortName: 'Phone-PT',
    category: 'end_devices', badge: 'Voice Endpoint',
    description: 'Analog voice endpoint for telephone and voice gateway labs.',
    defaultPorts: ['Phone0'], defaultBandwidth: 10, defaultLatency: 5, iconShape: 'phone',
  },
  {
    type: 'tv_pt', name: 'TV-PT Smart Television', shortName: 'TV-PT',
    category: 'end_devices', badge: 'Home Endpoint',
    description: 'Smart television endpoint with Ethernet and wireless connectivity.',
    defaultPorts: ['Ethernet0', 'Wireless0'], defaultBandwidth: 100, defaultLatency: 3, iconShape: 'smartphone',
  },
  {
    type: 'webcam_pt', name: 'Webcam-PT Network Camera', shortName: 'Webcam-PT',
    category: 'end_devices', badge: 'IoT Endpoint',
    description: 'Network video camera endpoint for surveillance and IoT layouts.',
    defaultPorts: ['FastEthernet0', 'Wireless0'], defaultBandwidth: 100, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'wireless_end_device', name: 'Wireless End Device-PT', shortName: 'Wireless-PT',
    category: 'end_devices', badge: 'Wi-Fi Client',
    description: 'Generic wireless client for laptops, tablets, and sensor associations.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 150, defaultLatency: 4, iconShape: 'laptop',
  },
  {
    type: 'motion_sensor', name: 'Motion Detector-PT', shortName: 'Motion',
    category: 'end_devices', badge: 'IoT Sensor',
    description: 'Smart-home motion sensor endpoint.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'temperature_sensor', name: 'Temperature Monitor-PT', shortName: 'Temp-Sensor',
    category: 'end_devices', badge: 'IoT Sensor',
    description: 'Environmental monitoring sensor endpoint.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'smart_light', name: 'Smart Light-PT', shortName: 'Light',
    category: 'end_devices', badge: 'IoT Actuator',
    description: 'Addressable smart lighting endpoint for a home automation network.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'smart_door', name: 'Smart Door-PT', shortName: 'Door',
    category: 'end_devices', badge: 'IoT Actuator',
    description: 'Connected door lock endpoint for a home automation network.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'fan_pt', name: 'Fan-PT Smart Fan', shortName: 'Fan',
    category: 'end_devices', badge: 'IoT Actuator',
    description: 'Connected fan endpoint for a smart building layout.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'sprinkler_pt', name: 'Sprinkler-PT Smart Sprinkler', shortName: 'Sprinkler',
    category: 'end_devices', badge: 'IoT Actuator',
    description: 'Connected sprinkler endpoint for a smart building layout.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'garage_door_pt', name: 'Garage Door-PT', shortName: 'Garage-Door',
    category: 'end_devices', badge: 'IoT Actuator',
    description: 'Connected garage door endpoint for home automation labs.',
    defaultPorts: ['Wireless0'], defaultBandwidth: 10, defaultLatency: 3, iconShape: 'iot',
  },
  {
    type: 'registration_server', name: 'Registration Server-PT', shortName: 'REG-Server',
    category: 'end_devices', badge: 'IoT Services',
    description: 'Server endpoint used by Packet Tracer IoT registration and monitoring labs.',
    defaultPorts: ['FastEthernet0', 'GigabitEthernet0'], defaultBandwidth: 1000, defaultLatency: 1.5, iconShape: 'server',
  },
];

export const CISCO_CABLES: CableDefinition[] = [
  {
    type: 'auto', name: 'Auto-Detect Cable', color: '#7C3AED', strokeDash: '2,3', defaultSpeed: 1000,
    description: 'Chooses a compatible cable automatically when two devices are connected.',
    recommendedUse: 'Let the editor choose the connection type',
  },
  {
    type: 'copper_straight',
    name: 'Copper Straight-Through',
    color: '#0F172A',
    strokeDash: undefined,
    defaultSpeed: 1000,
    description: 'Standard RJ-45 patch cable for connecting unlike devices (e.g., Switch to Router, Switch to PC).',
    recommendedUse: 'Switch ↔ Router, Switch ↔ PC/Server',
  },
  {
    type: 'copper_cross',
    name: 'Copper Cross-Over',
    color: '#EA580C',
    strokeDash: '6,4',
    defaultSpeed: 1000,
    description: 'Inverted pinout RJ-45 cable for connecting like devices without Auto-MDIX (e.g., Switch to Switch, Router to Router).',
    recommendedUse: 'Switch ↔ Switch, Router ↔ Router, PC ↔ PC',
  },
  {
    type: 'fiber',
    name: 'Fiber Optic Cable',
    color: '#EAB308',
    strokeDash: '8,3',
    defaultSpeed: 10000,
    description: 'High-speed 10 Gigabit optical fiber cable with LC connectors for core router-to-router and backbone links.',
    recommendedUse: 'High-speed Backbone & Datacenter Trunks',
  },
  {
    type: 'serial',
    name: 'Serial DCE / DTE Cable',
    color: '#DC2626',
    strokeDash: '4,2',
    defaultSpeed: 2,
    description: 'Synchronous WAN V.35 / Smart-Serial cable connecting routers across long distance leased lines.',
    recommendedUse: 'WAN Router ↔ WAN Router (Clocked)',
  },
  {
    type: 'phone',
    name: 'Telephone Line (RJ-11)',
    color: '#0D9488',
    strokeDash: '3,3',
    defaultSpeed: 24,
    description: 'Standard twisted pair analog telephone line connecting DSL modems to provider DSLAMs.',
    recommendedUse: 'DSL Modem ↔ WAN Cloud',
  },
  {
    type: 'coaxial',
    name: 'Coaxial Cable (RG-6)',
    color: '#64748B',
    strokeDash: undefined,
    defaultSpeed: 500,
    description: '75-ohm shielded coaxial cable for CATV and cable modem connections.',
    recommendedUse: 'Cable Modem ↔ Splitter / Cloud',
  },
  {
    type: 'wireless', name: 'Wireless Association', color: '#06B6D4', strokeDash: '2,5', defaultSpeed: 300,
    description: 'Radio link between wireless-capable devices or an access point and client.',
    recommendedUse: 'Access Point / Wireless Router ↔ Wireless Client',
  },
  {
    type: 'usb', name: 'USB Management Cable', color: '#9333EA', strokeDash: '2,2', defaultSpeed: 1,
    description: 'Visual-only local management connection; it does not carry routed simulation traffic.',
    recommendedUse: 'PC USB ↔ compatible device USB (management only)',
    simulationSupported: false,
  },
  {
    type: 'octal', name: 'Octal Rollover Cable', color: '#A855F7', strokeDash: '4,2', defaultSpeed: 1,
    description: 'Visual-only out-of-band management cable for terminal-server console lines.',
    recommendedUse: 'Terminal Server ↔ device console (management only)',
    simulationSupported: false,
  },
  {
    type: 'console',
    name: 'Console Rollover Cable',
    color: '#2563EB',
    strokeDash: undefined,
    defaultSpeed: 1,
    description: 'Light blue RJ-45 to DB-9 rollover cable for out-of-band serial console terminal management.',
    recommendedUse: 'PC Terminal ↔ Router/Switch Console Port',
    simulationSupported: false,
  },
];

/** Infer the Packet Tracer-style cable for a pair; the saved link always stores a concrete type. */
export function inferCableType(source: NetworkNode, destination: NetworkNode): Exclude<CableType, 'auto'> {
  const pair = new Set([source.type, destination.type]);
  if ((pair.has('cable_modem') || pair.has('coaxial_splitter')) &&
      (pair.has('cable_modem') || pair.has('coaxial_splitter') || pair.has('cloud_pt'))) return 'coaxial';
  if (pair.has('dsl_modem') && (pair.has('dslam_pt') || pair.has('cloud_pt'))) return 'phone';
  const wirelessClients = new Set<NodeType>([
    'laptop', 'tablet', 'smartphone', 'wireless_end_device', 'tv_pt', 'webcam_pt',
    'motion_sensor', 'temperature_sensor', 'smart_light', 'smart_door', 'fan_pt',
    'sprinkler_pt', 'garage_door_pt',
  ]);
  const hasWirelessAccess = ['ap_pt', 'wrt300n', 'home_gateway', 'cell_tower'].some((type) => pair.has(type as NodeType));
  if (hasWirelessAccess && (wirelessClients.has(source.type) || wirelessClients.has(destination.type))) return 'wireless';

  const sourceCategory = source.category || getHardwareDefinition(source.type).category;
  const destinationCategory = destination.category || getHardwareDefinition(destination.type).category;
  const sourceInfra = sourceCategory !== 'end_devices';
  const destinationInfra = destinationCategory !== 'end_devices';
  if (!sourceInfra && !destinationInfra) return 'copper_cross';
  if (sourceInfra && destinationInfra && sourceCategory === destinationCategory &&
      ['routers', 'switches', 'hubs'].includes(sourceCategory)) return 'copper_cross';
  return 'copper_straight';
}

export function suggestPortName(node: NetworkNode, cableType: Exclude<CableType, 'auto'>): string {
  const ports = node.interfaces?.map((port) => port.name) || getHardwareDefinition(node.type, node.category).defaultPorts;
  const patterns: Partial<Record<Exclude<CableType, 'auto'>, RegExp>> = {
    copper_straight: /ethernet|fastethernet|gigabitethernet|ten.?gig/i,
    copper_cross: /ethernet|fastethernet|gigabitethernet|ten.?gig/i,
    fiber: /fiber|sfp|ethernet|fastethernet|gigabitethernet|ten.?gig/i,
    serial: /serial/i,
    console: /console|rs.?232/i,
    phone: /phone|rj.?11|dsl/i,
    coaxial: /coax|rf|cable/i,
    wireless: /wireless|ssid|radio|cellular/i,
    usb: /usb/i,
    octal: /octal|console|serial/i,
  };
  return ports.find((port) => patterns[cableType]?.test(port)) || ports[0] || 'Port0';
}

// Helper to instantiate a new node with full Cisco specifications
export function createCiscoNode(
  hardware: CiscoHardwareItem,
  existingNodes: NetworkNode[],
  customX?: number,
  customY?: number
): NetworkNode {
  const typeCount = existingNodes.filter((n) => n.type === hardware.type).length + 1;
  const prefix = hardware.shortName.replace(/[^A-Za-z0-9]/g, '');
  const id = `${prefix}-${typeCount}`;

  const lastOctet = (existingNodes.length % 250) + 10;
  const ipAddress = `192.168.1.${lastOctet}`;

  const interfaces: DeviceInterface[] = hardware.defaultPorts.map((portName, idx) => ({
    id: `${id}_port_${idx}`,
    name: portName,
    speedMbps: hardware.defaultBandwidth,
    ipAddress: idx === 0 ? ipAddress : undefined,
    subnetMask: idx === 0 ? '255.255.255.0' : undefined,
    macAddress: `00:1C:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(Math.random() * 89 + 10)}:${Math.floor(Math.random() * 89 + 10)}`,
    isUp: true,
  }));

  return {
    id,
    type: hardware.type,
    label: `${hardware.shortName} (${id})`,
    category: hardware.category,
    model: hardware.name,
    ip: ipAddress,
    subnet: '255.255.255.0',
    gateway: '192.168.1.1',
    interfaces,
    x: customX ?? 360 + (Math.random() * 120 - 60),
    y: customY ?? 240 + (Math.random() * 120 - 60),
  };
}

// Find hardware definition by NodeType
export function getHardwareDefinition(type: NodeType, category?: CiscoDeviceCategory): CiscoHardwareItem {
  const found = CISCO_HARDWARE_CATALOG.find((h) => h.type === type);
  if (found) return found;

  if (type === 'custom_device' && category) {
    const iconByCategory: Record<CiscoDeviceCategory, CiscoHardwareItem['iconShape']> = {
      routers: 'router', switches: 'switch', hubs: 'hub', wireless: 'wireless',
      security: 'firewall', wan: 'cloud', end_devices: 'pc',
    };
    return {
      type, name: 'Custom Packet Tracer model', shortName: 'Custom', category,
      badge: 'Custom model', description: 'User-defined model category.', defaultPorts: [],
      defaultBandwidth: 1000, defaultLatency: 2, iconShape: iconByCategory[category],
    };
  }

  // Fallback if legacy 'router' | 'pc' | 'server'
  if (type === 'router') return CISCO_HARDWARE_CATALOG[0]; // 2911
  if (type === 'pc' || type === 'host') return CISCO_HARDWARE_CATALOG.find((h) => h.type === 'pc')!;
  if (type === 'server') return CISCO_HARDWARE_CATALOG.find((h) => h.type === 'server')!;
  return CISCO_HARDWARE_CATALOG[0];
}
