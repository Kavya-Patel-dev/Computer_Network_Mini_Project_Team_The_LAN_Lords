import { NetworkLink, NetworkNode, NodeType, Topology, isHostNode, isRoutingNode } from '../types/network';
import { CISCO_HARDWARE_CATALOG, inferCableType } from '../mock/ciscoHardware';

export type Redundancy = 'none' | 'backup' | 'full';

export interface DepartmentSpec {
  name: string;
  pc: number;
  laptop: number;
  ip_phone: number;
  printer: number;
  tablet: number;
  smartphone: number;
  iot: number;
}

export interface TopologyGeneratorOptions {
  name: string;
  routerCount: number;
  routerModel: NodeType;
  departments: DepartmentSpec[];
  servers: number;
  redundancy: Redundancy;
  backboneBandwidthMbps: number;
  accessBandwidthMbps: number;
}

const ENDPOINT_LABELS: Record<keyof Omit<DepartmentSpec, 'name'>, string> = {
  pc: 'PC', laptop: 'Laptop', ip_phone: 'IP Phone', printer: 'Printer',
  tablet: 'Tablet', smartphone: 'Smartphone', iot: 'IoT Device',
};

const clampInt = (value: number, min: number, max: number) => Math.max(min, Math.min(max, Math.floor(value)));

export function generateTopology(options: TopologyGeneratorOptions): Topology {
  const { name, departments, routerCount, routerModel, redundancy } = options;
  if (!Number.isInteger(routerCount) || routerCount < 5 || routerCount > 50) {
    throw new Error('Choose between 5 and 50 routers for simulation.');
  }
  if (departments.length < 1 || departments.length > 20) {
    throw new Error('Choose between 1 and 20 departments.');
  }
  if (!Number.isFinite(options.backboneBandwidthMbps) || options.backboneBandwidthMbps <= 0 ||
      !Number.isFinite(options.accessBandwidthMbps) || options.accessBandwidthMbps <= 0) {
    throw new Error('Backbone and access bandwidths must be positive numbers.');
  }
  const hardware = CISCO_HARDWARE_CATALOG.find((item) => item.type === routerModel && item.category === 'routers');
  if (!hardware) throw new Error('Select a supported router model.');

  const nodes: NetworkNode[] = [];
  const links: NetworkLink[] = [];
  for (let index = 0; index < routerCount; index += 1) {
    const angle = (2 * Math.PI * index) / routerCount;
    nodes.push({
      id: `R${index + 1}`, type: hardware.type, category: 'routers', model: hardware.name,
      label: `${hardware.shortName} R${index + 1}`, x: 450 + Math.cos(angle) * 300, y: 270 + Math.sin(angle) * 210,
    });
  }

  let linkIndex = 0;
  const pairs = new Set<string>();
  const addLink = (src: NetworkNode, dst: NetworkNode, bandwidth: number, latency: number) => {
    const key = [src.id, dst.id].sort().join('|');
    if (pairs.has(key)) return;
    pairs.add(key);
    let cableType = inferCableType(src, dst);
    if (bandwidth > 1000 && isRoutingNode(src.type, src.simulationRole) && isRoutingNode(dst.type, dst.simulationRole)) cableType = 'fiber';
    linkIndex += 1;
    links.push({
      id: `L${linkIndex}`, src: src.id, dst: dst.id, bandwidth_mbps: bandwidth,
      latency_ms: latency, loss_percent: 0.01, status: 'active', cableType,
    });
  };

  const routers = nodes.filter((node) => isRoutingNode(node.type, node.simulationRole));
  if (redundancy === 'none') {
    for (let index = 1; index < routers.length; index += 1) addLink(routers[0], routers[index], options.backboneBandwidthMbps, 2);
  } else if (redundancy === 'backup') {
    for (let index = 0; index < routers.length; index += 1) addLink(routers[index], routers[(index + 1) % routers.length], options.backboneBandwidthMbps, 2);
    for (let index = 0; index < Math.floor(routers.length / 2); index += 1) {
      addLink(routers[index], routers[(index + 2) % routers.length], options.backboneBandwidthMbps, 2);
    }
  } else {
    for (let left = 0; left < routers.length; left += 1) {
      for (let right = left + 1; right < routers.length; right += 1) addLink(routers[left], routers[right], options.backboneBandwidthMbps, 2);
    }
  }

  const endpointTotals: Record<string, number> = {};
  const totalEndpoints = departments.reduce((sum, department) =>
    sum + Object.entries(ENDPOINT_LABELS).reduce((subtotal, [kind]) => subtotal + clampInt(Number(department[kind as keyof DepartmentSpec]), 0, 100), 0), 0);
  if (totalEndpoints + options.servers < 2) throw new Error('Add at least two endpoint devices or servers so traffic has source and destination hosts.');
  if (totalEndpoints + options.servers > 500) throw new Error('The generated topology is limited to 500 endpoint devices.');

  const addEndpoint = (type: NodeType, label: string, prefix: string, department: string, routerIndex: number, x: number, y: number) => {
    endpointTotals[prefix] = (endpointTotals[prefix] || 0) + 1;
    const node: NetworkNode = {
      id: `${prefix}${endpointTotals[prefix]}`, type, label, category: 'end_devices', department, x, y,
    };
    nodes.push(node);
    addLink(node, routers[routerIndex], options.accessBandwidthMbps, 1);
  };

  departments.forEach((department, departmentIndex) => {
    const departmentName = department.name.trim() || `Department ${departmentIndex + 1}`;
    const routerIndex = departmentIndex % routers.length;
    const kinds = Object.keys(ENDPOINT_LABELS) as Array<keyof Omit<DepartmentSpec, 'name'>>;
    kinds.forEach((kind, kindIndex) => {
      const count = clampInt(Number(department[kind]), 0, 100);
      for (let index = 0; index < count; index += 1) {
        const hardwareItem = CISCO_HARDWARE_CATALOG.find((item) => item.type === kind);
        if (hardwareItem) {
          const x = 120 + departmentIndex * 260 + kindIndex * 18;
          const y = 480 + index * 28;
          addEndpoint(hardwareItem.type, `${departmentName} ${ENDPOINT_LABELS[kind]} ${index + 1}`, `${kind.toUpperCase()}-${departmentIndex + 1}-`, departmentName, routerIndex, x, y);
        }
      }
    });
  });

  const serverCount = clampInt(Number(options.servers), 0, 50);
  for (let index = 0; index < serverCount; index += 1) {
    addEndpoint('server', `Application Server ${index + 1}`, 'S', 'Shared Services', (index + 1) % routers.length, 260 + index * 100, 70);
  }

  // Guard the generator itself: every generated end device is a leaf and every core element is classified.
  if (nodes.some((node) => !isRoutingNode(node.type, node.simulationRole) && !isHostNode(node.type, node.simulationRole))) {
    throw new Error('A selected device is missing its simulation classification.');
  }
  return { id: crypto.randomUUID(), name: name.trim() || 'Generated Network', nodes, links };
}
