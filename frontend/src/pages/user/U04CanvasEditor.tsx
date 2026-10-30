import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useViewport } from '../../context/ViewportContext';
import { api } from '../../api/client';
import { Plan } from '../../types/plan';
import { 
  Topology, 
  NetworkNode, 
  NetworkLink, 
  CableType, 
  CiscoDeviceCategory,
  NodeType,
  isRoutingNode, 
  isHostNode 
} from '../../types/network';
import { 
  CISCO_HARDWARE_CATALOG, 
  CISCO_CABLES, 
  CiscoHardwareItem, 
  createCiscoNode, 
  getHardwareDefinition,
  inferCableType,
  suggestPortName,
} from '../../mock/ciscoHardware';
import { TopologyDiagram } from '../../components/canvas/TopologyDiagram';
import { TopologyListView } from '../../components/canvas/TopologyListView';
import { CiscoDeviceGlyph } from '../../components/canvas/CiscoDeviceGlyph';
import { 
  Search, 
  RotateCcw, 
  RotateCw, 
  Sparkles, 
  Sliders, 
  CheckCircle, 
  AlertTriangle, 
  ArrowRight, 
  List, 
  Trash2, 
  Copy, 
  Link2, 
  Plus, 
  Info, 
  Grid, 
  Maximize2, 
  Minimize2,
  X, 
  Network, 
  Layers, 
  Cpu, 
  Wifi, 
  Shield, 
  Cloud, 
  Laptop, 
  Cable,
  Check,
  ChevronLeft,
  ChevronRight,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  GripHorizontal,
  GripVertical
} from 'lucide-react';

export const U04CanvasEditor: React.FC = () => {
  const { navigate, mode, currentPath } = useViewport();
  const planId = currentPath.split('/')[2] || '';
  const blankTopology: Topology = { id: planId, name: 'New routing topology', nodes: [], links: [] };

  // Primary topology state with history stack for undo/redo
  const [topology, setTopology] = useState<Topology>(blankTopology);
  const [history, setHistory] = useState<Topology[]>([blankTopology]);
  const [historyIndex, setHistoryIndex] = useState<number>(0);

  // Selection states
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<NetworkLink | null>(null);

  // Panel layout controls & Resizable Windows
  const [leftShelfOpen, setLeftShelfOpen] = useState<boolean>(true);
  const [rightInspectorOpen, setRightInspectorOpen] = useState<boolean>(false);
  const [fullscreenMode, setFullscreenMode] = useState<boolean>(false);

  // Dynamic Resizable Widths (drag to resize)
  const [leftShelfWidth, setLeftShelfWidth] = useState<number>(280);
  const [rightInspectorWidth, setRightInspectorWidth] = useState<number>(320);
  const [isResizingLeft, setIsResizingLeft] = useState<boolean>(false);
  const [isResizingRight, setIsResizingRight] = useState<boolean>(false);
  const workspaceRef = useRef<HTMLDivElement>(null);

  // Draggable Resizer Handler for Left Cisco Shelf
  const handleStartResizeLeft = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
    const startX = e.clientX;
    const initialWidth = leftShelfWidth;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const delta = moveEvent.clientX - startX;
      let newWidth = initialWidth + delta;
      if (newWidth < 120) {
        setLeftShelfOpen(false);
      } else {
        if (!leftShelfOpen) setLeftShelfOpen(true);
        newWidth = Math.max(180, Math.min(600, newWidth));
        setLeftShelfWidth(newWidth);
      }
    };

    const handlePointerUp = () => {
      setIsResizingLeft(false);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  // Draggable Resizer Handler for Right Inspector
  const handleStartResizeRight = (e: React.PointerEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
    const startX = e.clientX;
    const initialWidth = rightInspectorWidth;

    const handlePointerMove = (moveEvent: PointerEvent) => {
      const delta = startX - moveEvent.clientX;
      let newWidth = initialWidth + delta;
      if (newWidth < 120) {
        setRightInspectorOpen(false);
      } else {
        if (!rightInspectorOpen) setRightInspectorOpen(true);
        newWidth = Math.max(200, Math.min(650, newWidth));
        setRightInspectorWidth(newWidth);
      }
    };

    const handlePointerUp = () => {
      setIsResizingRight(false);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  };

  // Inspector & Shelf tabs
  const [activeInspectorTab, setActiveInspectorTab] = useState<'properties' | 'validation' | 'summary'>('properties');
  const [shelfCategory, setShelfCategory] = useState<CiscoDeviceCategory | 'cables'>('routers');
  const [searchQuery, setSearchQuery] = useState('');
  const [customDeviceOpen, setCustomDeviceOpen] = useState(false);
  const [customDeviceName, setCustomDeviceName] = useState('Custom Cisco device');
  const [customDeviceCategory, setCustomDeviceCategory] = useState<CiscoDeviceCategory>('routers');
  const [customPortCount, setCustomPortCount] = useState(4);
  const [customPortSpeed, setCustomPortSpeed] = useState(1000);

  // Cable tool
  const [activeCableType, setActiveCableType] = useState<CableType>('copper_straight');
  const [connectingSourceId, setConnectingSourceId] = useState<string | null>(null);

  // Canvas settings
  const [gridSnap, setGridSnap] = useState(true);
  const [showListView, setShowListView] = useState(false);
  const [saveStatus, setSaveStatus] = useState('All changes saved');
  const [planLoaded, setPlanLoaded] = useState(false);

  useEffect(() => {
    if (!planId) {
      setSaveStatus('Plan identifier is missing');
      return;
    }
    let active = true;
    api.get<Plan>(`/records/${encodeURIComponent(planId)}`).then((plan) => {
      if (!active) return;
      const loadedTopology = plan.topology as Topology;
      setTopology(loadedTopology);
      setHistory([loadedTopology]);
      setHistoryIndex(0);
      setPlanLoaded(true);
      setSaveStatus('Loaded from your saved plan');
    }).catch((error) => {
      if (active) setSaveStatus(error instanceof Error ? error.message : 'Could not load saved plan');
    });
    return () => { active = false; };
  }, [planId]);

  useEffect(() => {
    if (!planLoaded || !planId) return;
    setSaveStatus('Saving changes…');
    const timeout = window.setTimeout(() => {
      api.patch(`/records/${encodeURIComponent(planId)}`, {
        topology: { ...topology, id: planId },
      }).then(() => setSaveStatus('Saved to your account'))
        .catch((error) => setSaveStatus(error instanceof Error ? `Save failed: ${error.message}` : 'Save failed'));
    }, 800);
    return () => window.clearTimeout(timeout);
  }, [topology, planId, planLoaded]);

  // Push new state to undo/redo history
  const commitTopology = useCallback(
    (newTopology: Topology, statusMessage = 'Saved just now') => {
      setTopology(newTopology);
      setHistory((prev) => {
        const sliced = prev.slice(0, historyIndex + 1);
        return [...sliced, newTopology];
      });
      setHistoryIndex((prev) => prev + 1);
      setSaveStatus(statusMessage);
    },
    [historyIndex]
  );

  // Undo / Redo handlers
  const handleUndo = useCallback(() => {
    if (historyIndex > 0) {
      const nextIndex = historyIndex - 1;
      setHistoryIndex(nextIndex);
      setTopology(history[nextIndex]);
      setSelectedNode(null);
      setSelectedLink(null);
      setSaveStatus('Undone');
    }
  }, [history, historyIndex]);

  const handleRedo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const nextIndex = historyIndex + 1;
      setHistoryIndex(nextIndex);
      setTopology(history[nextIndex]);
      setSelectedNode(null);
      setSelectedLink(null);
      setSaveStatus('Redone');
    }
  }, [history, historyIndex]);

  // Global Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        if (e.shiftKey) {
          e.preventDefault();
          handleRedo();
        } else {
          e.preventDefault();
          handleUndo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        e.preventDefault();
        handleRedo();
      } else if (e.key === 'Delete' || e.key === 'Backspace') {
        const tag = (e.target as HTMLElement).tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA') {
          if (selectedNode) {
            handleDeleteNode(selectedNode.id);
          } else if (selectedLink) {
            handleDeleteLink(selectedLink.id);
          }
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleUndo, handleRedo, selectedNode, selectedLink]);

  // Update node position
  const handleUpdateNodePosition = (nodeId: string, x: number, y: number) => {
    const updated = topology.nodes.map((n) => (n.id === nodeId ? { ...n, x, y } : n));
    commitTopology({ ...topology, nodes: updated }, 'Position updated');
    if (selectedNode && selectedNode.id === nodeId) {
      setSelectedNode({ ...selectedNode, x, y });
    }
  };

  // Add new Cisco Device from click
  const handleAddCiscoDevice = (hardware: CiscoHardwareItem, customX?: number, customY?: number) => {
    const newNode = createCiscoNode(hardware, topology.nodes, customX, customY);
    const updatedNodes = [...topology.nodes, newNode];
    commitTopology({ ...topology, nodes: updatedNodes }, `Added ${hardware.shortName}`);
    setSelectedNode(newNode);
    setSelectedLink(null);
    setRightInspectorOpen(true);
  };

  // Add new Cisco Device from drop onto canvas
  const handleDropDevice = (type: NodeType, x: number, y: number) => {
    const hw = getHardwareDefinition(type);
    handleAddCiscoDevice(hw, x, y);
  };

  const handleAddCustomDevice = () => {
    const modelName = customDeviceName.trim();
    if (!modelName) return;
    const iconByCategory: Record<CiscoDeviceCategory, CiscoHardwareItem['iconShape']> = {
      routers: 'router', switches: 'switch', hubs: 'hub', wireless: 'wireless',
      security: 'firewall', wan: 'cloud', end_devices: 'pc',
    };
    const interfacePrefix = customPortSpeed >= 1000 ? 'GigabitEthernet0/' : 'FastEthernet0/';
    const hardware: CiscoHardwareItem = {
      type: 'custom_device', name: modelName, shortName: 'CUSTOM', category: customDeviceCategory,
      badge: 'Custom model', description: 'User-defined Packet Tracer device model.',
      defaultPorts: Array.from({ length: customPortCount }, (_, index) => interfacePrefix + (index + 1)),
      defaultBandwidth: customPortSpeed, defaultLatency: 2, iconShape: iconByCategory[customDeviceCategory],
    };
    const newNode = createCiscoNode(hardware, topology.nodes);
    newNode.type = 'custom_device';
    newNode.model = modelName;
    newNode.label = `${modelName} (${newNode.id})`;
    newNode.simulationRole = customDeviceCategory === 'end_devices' ? 'host' : 'router';
    commitTopology({ ...topology, nodes: [...topology.nodes, newNode] }, `Added custom ${modelName}`);
    setSelectedNode(newNode);
    setSelectedLink(null);
    setRightInspectorOpen(true);
    setCustomDeviceOpen(false);
  };

  // Add Link between two devices
  const handleAddLink = (srcId: string, dstId: string, cableType: CableType) => {
    const exists = topology.links.some(
      (l) => l.simulationIncluded !== false && ((l.src === srcId && l.dst === dstId) || (l.src === dstId && l.dst === srcId))
    );
    if (exists) {
      setSaveStatus('Link already exists');
      return;
    }

    const sourceNode = topology.nodes.find((node) => node.id === srcId);
    const destinationNode = topology.nodes.find((node) => node.id === dstId);
    if (!sourceNode || !destinationNode) {
      setSaveStatus('Choose two existing devices before connecting a cable');
      return;
    }
    const resolvedCableType = cableType === 'auto' ? inferCableType(sourceNode, destinationNode) : cableType;
    const cableDef = CISCO_CABLES.find((c) => c.type === resolvedCableType) || CISCO_CABLES[1];
    const newLinkId = `L_${srcId}_${dstId}`;

    const newLink: NetworkLink = {
      id: newLinkId,
      src: srcId,
      dst: dstId,
      bandwidth_mbps: cableDef.defaultSpeed,
      latency_ms: resolvedCableType === 'fiber' ? 0.8 : resolvedCableType === 'serial' ? 12 : resolvedCableType === 'wireless' ? 4 : 2.0,
      loss_percent: 0,
      status: 'active',
      cableType: resolvedCableType,
      ...(cableDef.simulationSupported === false ? { simulationIncluded: false } : {}),
      srcPort: suggestPortName(sourceNode, resolvedCableType),
      dstPort: suggestPortName(destinationNode, resolvedCableType),
    };

    const updatedLinks = [...topology.links, newLink];
    commitTopology({ ...topology, links: updatedLinks }, `Connected ${srcId} to ${dstId} with ${cableDef.name}`);
    setSelectedLink(newLink);
    setSelectedNode(null);
    setConnectingSourceId(null);
    setRightInspectorOpen(true);
  };

  const handleAutoConnect = () => {
    const infrastructure = topology.nodes.filter((node) => isRoutingNode(node.type, node.simulationRole));
    const hosts = topology.nodes.filter((node) => isHostNode(node.type, node.simulationRole));
    if (!infrastructure.length) {
      setSaveStatus('Add at least one router, switch, or other infrastructure device before auto-connect');
      return;
    }

    const parent = new Map(infrastructure.map((node) => [node.id, node.id]));
    const find = (id: string): string => {
      const current = parent.get(id) || id;
      if (current === id) return id;
      const root = find(current);
      parent.set(id, root);
      return root;
    };
    const join = (left: string, right: string) => {
      const a = find(left), b = find(right);
      if (a !== b) parent.set(b, a);
    };
    const infrastructureIds = new Set(infrastructure.map((node) => node.id));
    const simulationLinks = topology.links.filter((link) => link.simulationIncluded !== false);
    simulationLinks.forEach((link) => {
      if (infrastructureIds.has(link.src) && infrastructureIds.has(link.dst)) join(link.src, link.dst);
    });

    const newLinks: NetworkLink[] = [];
    const pairs = new Set(topology.links.filter((link) => link.simulationIncluded !== false).map((link) => [link.src, link.dst].sort().join('|')));
    const linkIds = new Set(topology.links.map((link) => link.id));
    const createAutoLink = (source: NetworkNode, destination: NetworkNode, bandwidth: number, latency: number) => {
      const pair = [source.id, destination.id].sort().join('|');
      if (pairs.has(pair)) return false;
      pairs.add(pair);
      const cableType = inferCableType(source, destination);
      const cable = CISCO_CABLES.find((item) => item.type === cableType);
      let id = `AUTO_${source.id}_${destination.id}`;
      let suffix = 1;
      while (linkIds.has(id)) { id = `AUTO_${source.id}_${destination.id}_${suffix}`; suffix += 1; }
      linkIds.add(id);
      newLinks.push({
        id, src: source.id, dst: destination.id, cableType,
        bandwidth_mbps: Math.min(bandwidth, cable?.defaultSpeed ?? bandwidth), latency_ms: latency,
        loss_percent: 0, status: 'active',
        srcPort: suggestPortName(source, cableType),
        dstPort: suggestPortName(destination, cableType),
      });
      return true;
    };

    // Join disconnected infrastructure components by their nearest device pair.
    while (new Set(infrastructure.map((node) => find(node.id))).size > 1) {
      let nearest: { source: NetworkNode; destination: NetworkNode; distance: number } | undefined;
      for (let left = 0; left < infrastructure.length; left += 1) {
        for (let right = left + 1; right < infrastructure.length; right += 1) {
          const a = infrastructure[left], b = infrastructure[right];
          if (find(a.id) === find(b.id)) continue;
          const distance = Math.hypot((a.x ?? left * 100) - (b.x ?? right * 100), (a.y ?? 0) - (b.y ?? 0));
          if (!nearest || distance < nearest.distance) nearest = { source: a, destination: b, distance };
        }
      }
      if (!nearest) break;
      createAutoLink(nearest.source, nearest.destination, 1000, 2);
      join(nearest.source.id, nearest.destination.id);
    }

    // Attach each unattached endpoint to its nearest infrastructure device.
    hosts.forEach((host) => {
      const hasAccessLink = simulationLinks.some((link) =>
        (link.src === host.id && infrastructureIds.has(link.dst)) ||
        (link.dst === host.id && infrastructureIds.has(link.src))) || newLinks.some((link) =>
        (link.src === host.id && infrastructureIds.has(link.dst)) ||
        (link.dst === host.id && infrastructureIds.has(link.src)));
      if (hasAccessLink) return;
      const closest = infrastructure.reduce((best, candidate) => {
        const distance = Math.hypot((host.x ?? 0) - (candidate.x ?? 0), (host.y ?? 0) - (candidate.y ?? 0));
        return !best || distance < best.distance ? { node: candidate, distance } : best;
      }, undefined as { node: NetworkNode; distance: number } | undefined);
      if (closest) createAutoLink(host, closest.node, 100, 1);
    });

    if (!newLinks.length) {
      setSaveStatus('All routing devices and endpoints already have simulated connections');
      return;
    }
    commitTopology({ ...topology, links: [...topology.links, ...newLinks] }, `Auto-connected ${newLinks.length} device pairs with compatible cables`);
  };

  // Delete Node
  const handleDeleteNode = (id: string) => {
    const updatedNodes = topology.nodes.filter((n) => n.id !== id);
    const updatedLinks = topology.links.filter((l) => l.src !== id && l.dst !== id);
    commitTopology({ ...topology, nodes: updatedNodes, links: updatedLinks }, `Deleted ${id}`);
    setSelectedNode(null);
  };

  // Duplicate Node
  const handleDuplicateNode = (node: NetworkNode) => {
    const hw = getHardwareDefinition(node.type, node.category);
    const newNode = createCiscoNode(hw, topology.nodes, (node.x ?? 100) + 40, (node.y ?? 100) + 40);
    newNode.label = `${node.label} Copy`;
    if (node.type === 'custom_device') {
      newNode.type = 'custom_device';
      newNode.model = node.model;
      newNode.category = node.category;
      newNode.simulationRole = node.simulationRole;
      newNode.interfaces = node.interfaces?.map((port) => ({ ...port, connectedTo: undefined }));
    }
    const updatedNodes = [...topology.nodes, newNode];
    commitTopology({ ...topology, nodes: updatedNodes }, `Duplicated ${node.id}`);
    setSelectedNode(newNode);
    setRightInspectorOpen(true);
  };

  // Delete Link
  const handleDeleteLink = (id: string) => {
    const updatedLinks = topology.links.filter((l) => l.id !== id);
    commitTopology({ ...topology, links: updatedLinks }, `Disconnected cable`);
    setSelectedLink(null);
  };

  // Auto-Layout Engine: organizes nodes cleanly into hierarchical tiers
  const handleAutoLayout = () => {
    const routers = topology.nodes.filter((n) => isRoutingNode(n.type, n.simulationRole));
    const switches = topology.nodes.filter((n) =>
      (n.category === 'switches' || n.category === 'hubs') && !isRoutingNode(n.type, n.simulationRole));
    const hosts = topology.nodes.filter((n) => isHostNode(n.type, n.simulationRole));
    const others = topology.nodes.filter(
      (n) => !isRoutingNode(n.type, n.simulationRole) && !switches.includes(n) && !hosts.includes(n)
    );

    const canvasWidth = 840;
    const startX = 80;

    // Position Routers (Top Tier)
    const routerSpacing = canvasWidth / Math.max(routers.length, 1);
    const updatedRouters = routers.map((r, i) => ({
      ...r,
      x: Math.round((startX + i * routerSpacing + routerSpacing / 2) / 20) * 20,
      y: 90,
    }));

    // Position Switches / Bridges (Middle Tier)
    const switchSpacing = canvasWidth / Math.max(switches.length, 1);
    const updatedSwitches = switches.map((s, i) => ({
      ...s,
      x: Math.round((startX + i * switchSpacing + switchSpacing / 2) / 20) * 20,
      y: 240,
    }));

    // Position Hosts / Leaves (Bottom Tier)
    const hostSpacing = canvasWidth / Math.max(hosts.length, 1);
    const updatedHosts = hosts.map((h, i) => ({
      ...h,
      x: Math.round((startX + i * hostSpacing + hostSpacing / 2) / 20) * 20,
      y: 400,
    }));

    // Position others (WAN/Security)
    const otherSpacing = canvasWidth / Math.max(others.length, 1);
    const updatedOthers = others.map((o, i) => ({
      ...o,
      x: Math.round((startX + i * otherSpacing + otherSpacing / 2) / 20) * 20,
      y: 520,
    }));

    const allRepositioned = [
      ...updatedRouters,
      ...updatedSwitches,
      ...updatedHosts,
      ...updatedOthers,
    ];

    commitTopology({ ...topology, nodes: allRepositioned }, 'Applied Auto-Layout');
  };

  // Filter hardware devices
  const filteredHardware = useMemo(() => {
    return CISCO_HARDWARE_CATALOG.filter((item) => {
      const matchesCategory = shelfCategory === item.category;
      const matchesSearch =
        searchQuery === '' ||
        item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.shortName.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.badge.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [shelfCategory, searchQuery]);

  // Validation rules engine
  const routerCount = topology.nodes.filter((n) => isRoutingNode(n.type, n.simulationRole)).length;
  const hostCount = topology.nodes.filter((n) => isHostNode(n.type, n.simulationRole)).length;

  const errors: string[] = [];
  const warnings: string[] = [];

  if (routerCount < 5) {
    errors.push(`Network requires at least 5 routing devices for Dijkstra/AI evaluation (currently ${routerCount}).`);
  }
  if (routerCount > 50) {
    errors.push(`Maximum 50 routing devices supported for discrete simulation (currently ${routerCount}).`);
  }
  if (hostCount < 2) {
    errors.push(`Network requires at least 2 host client/server devices to generate traffic demands.`);
  }

  const connectedNodeIds = new Set<string>();
  topology.links.filter((link) => link.simulationIncluded !== false).forEach((l) => {
    connectedNodeIds.add(l.src);
    connectedNodeIds.add(l.dst);
  });
  const orphanNodes = topology.nodes.filter((n) => !connectedNodeIds.has(n.id));
  if (orphanNodes.length > 0) {
    warnings.push(`${orphanNodes.length} devices have no active cable connections (${orphanNodes.map((n) => n.id).join(', ')}).`);
  }

  return (
    <div className={`flex flex-col h-full bg-brand-bg select-none ${fullscreenMode ? 'fixed inset-0 z-50 bg-brand-bg' : ''}`}>
      {/* Top Main Toolbar */}
      <div className="bg-brand-surface border-b border-brand-border px-4 py-2 flex items-center justify-between gap-3 z-20 shrink-0">
        {/* Left Side: Topology Name & Save Status & Shelf Toggle */}
        <div className="flex items-center gap-2">
          {/* Toggle Left Shelf Button */}
          <button
            onClick={() => setLeftShelfOpen(!leftShelfOpen)}
            className={`p-1.5 rounded-lg border text-caption font-semibold flex items-center gap-1.5 transition-colors ${
              leftShelfOpen
                ? 'bg-brand-primary/10 text-brand-primary border-brand-primary/30'
                : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
            }`}
            title={leftShelfOpen ? 'Collapse Cisco Shelf' : 'Open Cisco Shelf'}
          >
            {leftShelfOpen ? <PanelLeftClose className="w-4 h-4" /> : <PanelLeftOpen className="w-4 h-4" />}
            <span className="hidden md:inline font-mono text-xs">Cisco Shelf</span>
          </button>

          <div className="h-5 w-[1px] bg-brand-border mx-1" />

          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-brand-primary" />
            <input
              type="text"
              value={topology.name}
              onChange={(e) => setTopology({ ...topology, name: e.target.value })}
              className="text-h3 font-bold bg-transparent text-brand-text-primary border-b border-transparent hover:border-brand-border focus:border-brand-primary px-1 py-0.5 focus:outline-none"
              title="Click to rename topology"
            />
          </div>
          <span className="hidden sm:inline text-[11px] text-brand-text-muted font-mono bg-brand-bg px-2 py-0.5 rounded border border-brand-border">
            {saveStatus}
          </span>
        </div>

        {/* Center / Right Action Controls */}
        <div className="flex items-center gap-2">
          {/* Undo / Redo */}
          <div className="flex items-center gap-0.5 bg-brand-bg border border-brand-border rounded-lg p-0.5 shadow-sm">
            <button
              onClick={handleUndo}
              disabled={historyIndex === 0}
              className={`p-1.5 rounded transition-colors ${
                historyIndex > 0
                  ? 'text-brand-text-primary hover:bg-brand-surface'
                  : 'text-brand-text-muted cursor-not-allowed opacity-40'
              }`}
              title="Undo (Ctrl+Z)"
            >
              <RotateCcw className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleRedo}
              disabled={historyIndex >= history.length - 1}
              className={`p-1.5 rounded transition-colors ${
                historyIndex < history.length - 1
                  ? 'text-brand-text-primary hover:bg-brand-surface'
                  : 'text-brand-text-muted cursor-not-allowed opacity-40'
              }`}
              title="Redo (Ctrl+Y)"
            >
              <RotateCw className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Grid Snap Toggle */}
          <button
            onClick={() => setGridSnap(!gridSnap)}
            className={`px-2.5 py-1.5 rounded-lg text-caption font-semibold flex items-center gap-1.5 border transition-colors ${
              gridSnap
                ? 'bg-brand-primary/10 text-brand-primary border-brand-primary/30'
                : 'bg-brand-bg text-brand-text-muted border-brand-border'
            }`}
            title="Toggle Grid Snapping (20px)"
          >
            <Grid className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-xs">Snap</span>
          </button>

          {/* Auto Layout Button */}
          <button
            onClick={handleAutoLayout}
            className="px-2.5 py-1.5 rounded-lg bg-brand-bg hover:bg-brand-surface text-brand-text-secondary hover:text-brand-text-primary border border-brand-border text-caption font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            title="Auto-organize topology into tiers"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden sm:inline text-xs">Auto Layout</span>
          </button>

          <button
            onClick={handleAutoConnect}
            className="px-2.5 py-1.5 rounded-lg bg-brand-primary/10 hover:bg-brand-primary/15 text-brand-primary border border-brand-primary/30 text-caption font-semibold flex items-center gap-1.5 transition-colors shadow-sm"
            title="Join disconnected infrastructure and attach unconnected endpoints using auto-detected cables"
          >
            <Link2 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline text-xs">Auto Connect</span>
          </button>

          {/* View Toggle */}
          <button
            onClick={() => setShowListView(!showListView)}
            className={`px-2.5 py-1.5 rounded-lg text-caption font-semibold flex items-center gap-1.5 border transition-colors ${
              showListView
                ? 'bg-brand-primary text-white border-brand-primary'
                : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
            }`}
          >
            <List className="w-3.5 h-3.5" />
            <span className="text-xs">{showListView ? 'Canvas' : 'List'}</span>
          </button>

          {/* Fullscreen Canvas Toggle */}
          <button
            onClick={() => setFullscreenMode(!fullscreenMode)}
            className={`p-1.5 rounded-lg border text-caption font-semibold flex items-center gap-1 transition-colors ${
              fullscreenMode
                ? 'bg-brand-primary text-white border-brand-primary'
                : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
            }`}
            title={fullscreenMode ? 'Exit Fullscreen' : 'Fullscreen Canvas'}
          >
            {fullscreenMode ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>

          {/* Toggle Inspector Button */}
          <button
            onClick={() => setRightInspectorOpen(!rightInspectorOpen)}
            className={`px-2.5 py-1.5 rounded-lg border text-caption font-semibold flex items-center gap-1.5 transition-colors ${
              rightInspectorOpen
                ? 'bg-brand-primary/10 text-brand-primary border-brand-primary/30'
                : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
            }`}
            title={rightInspectorOpen ? 'Close Inspector' : 'Open Inspector'}
          >
            {rightInspectorOpen ? <PanelRightClose className="w-4 h-4" /> : <PanelRightOpen className="w-4 h-4" />}
            <span className="hidden lg:inline text-xs">Inspector</span>
          </button>

          {/* Validation Pill */}
          <button
            onClick={() => {
              setActiveInspectorTab('validation');
              setRightInspectorOpen(true);
            }}
            className={`px-2.5 py-1 rounded-lg text-caption font-semibold flex items-center gap-1.5 border transition-colors ${
              errors.length > 0
                ? 'bg-rose-50 text-rose-800 border-rose-300 dark:bg-rose-950/40 dark:text-rose-300'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300 dark:bg-emerald-950/40 dark:text-emerald-300'
            }`}
          >
            {errors.length > 0 ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
                <span className="text-xs">{errors.length}</span>
              </>
            ) : (
              <>
                <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
                <span className="text-xs">Valid</span>
              </>
            )}
          </button>

          {/* Next Step Button */}
          <button
            onClick={() => navigate(`/plans/${planId}/edit/traffic`)}
            className="px-3.5 py-1.5 rounded-lg bg-brand-primary text-white text-xs font-semibold hover:opacity-90 flex items-center gap-1 shadow-sm"
          >
            <span>Next</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Workspace Body */}
      <div
        ref={workspaceRef}
        className="flex-1 flex overflow-hidden relative"
        style={{ cursor: isResizingLeft || isResizingRight ? 'col-resize' : undefined }}
      >
        {/* Left Drawer: Cisco Packet Tracer Hardware Shelf */}
        {leftShelfOpen && (
          <aside
            style={{ width: `${leftShelfWidth}px` }}
            className="bg-brand-surface border-r border-brand-border flex flex-col justify-between shrink-0 shadow-md z-10 select-none"
          >
            <div className="flex flex-col h-full">
              {/* Drawer Header */}
              <div className="p-2.5 border-b border-brand-border space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-overline text-brand-text-muted font-bold tracking-wider">
                    Cisco Hardware Shelf
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-brand-bg text-brand-text-secondary border border-brand-border">
                      Packet Tracer
                    </span>
                    <button
                      onClick={() => setLeftShelfOpen(false)}
                      className="p-1 text-brand-text-muted hover:text-brand-text-primary rounded"
                      title="Collapse Shelf"
                    >
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Search Bar */}
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-brand-text-muted absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    placeholder="Search 2911, 3560, ASA, PC..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-8 pr-3 py-1 bg-brand-bg border border-brand-border rounded-lg text-caption text-brand-text-primary focus:outline-none focus:border-brand-primary"
                  />
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-brand-text-muted hover:text-brand-text-primary"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  )}
                </div>

                {/* Category Pills */}
                <div className="grid grid-cols-4 gap-1 text-[11px] font-semibold">
                  <button
                    onClick={() => setShelfCategory('routers')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'routers'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Cpu className="w-3 h-3" />
                    <span className="text-[10px]">Routers</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('switches')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'switches'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Layers className="w-3 h-3" />
                    <span className="text-[10px]">Switches</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('hubs')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'hubs'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Network className="w-3 h-3" />
                    <span className="text-[10px]">Hubs</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('wireless')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'wireless'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Wifi className="w-3 h-3" />
                    <span className="text-[10px]">Wireless</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('security')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'security'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Shield className="w-3 h-3" />
                    <span className="text-[10px]">Security</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('wan')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'wan'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Cloud className="w-3 h-3" />
                    <span className="text-[10px]">WAN</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('end_devices')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'end_devices'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Laptop className="w-3 h-3" />
                    <span className="text-[10px]">Hosts</span>
                  </button>

                  <button
                    onClick={() => setShelfCategory('cables')}
                    className={`py-1 rounded flex flex-col items-center gap-0.5 border transition-colors ${
                      shelfCategory === 'cables'
                        ? 'bg-brand-primary text-white border-brand-primary'
                        : 'bg-brand-bg text-brand-text-secondary border-brand-border hover:bg-brand-surface'
                    }`}
                  >
                    <Cable className="w-3 h-3" />
                    <span className="text-[10px]">Cables</span>
                  </button>
                </div>
              </div>

              {/* Shelf Items List */}
              <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
                {shelfCategory === 'cables' ? (
                  /* Cables Selector */
                  <div className="space-y-1.5">
                    <p className="text-[10px] text-brand-text-muted pb-1">
                      Select cable, then click 2 devices or drag between port dots:
                    </p>
                    {CISCO_CABLES.map((cable) => {
                      const isSelected = activeCableType === cable.type;
                      return (
                        <div
                          key={cable.type}
                          onClick={() => setActiveCableType(cable.type)}
                          className={`p-2 rounded-lg border text-left cursor-pointer transition-all ${
                            isSelected
                              ? 'bg-brand-primary/10 border-brand-primary ring-1 ring-brand-primary'
                              : 'bg-brand-bg border-brand-border hover:border-brand-primary/50'
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <div className="flex items-center gap-2">
                              <div
                                className="w-3.5 h-3.5 rounded-full border border-brand-border shrink-0"
                                style={{ backgroundColor: cable.color }}
                              />
                              <span className="font-semibold text-xs text-brand-text-primary">
                                {cable.name}
                              </span>
                            </div>
                            {isSelected && <Check className="w-3.5 h-3.5 text-brand-primary" />}
                          </div>
                          <div className="flex items-center justify-between text-[10px] font-mono text-brand-text-secondary">
                            <span>{cable.recommendedUse}</span>
                            <span className="font-bold text-brand-primary">
                              {cable.defaultSpeed >= 1000 ? `${cable.defaultSpeed / 1000} Gbps` : `${cable.defaultSpeed} Mbps`}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  /* Hardware Devices List */
                  <div className="space-y-1.5">
                    <button
                      onClick={() => setCustomDeviceOpen((open) => !open)}
                      className="w-full p-2 rounded-lg bg-brand-primary/10 border border-brand-primary/30 text-brand-primary text-xs font-semibold text-left"
                    >
                      {customDeviceOpen ? 'Close custom model form' : '+ Add any/custom Packet Tracer model'}
                    </button>
                    {customDeviceOpen && <div className="p-3 rounded-lg border border-brand-primary/30 bg-brand-surface space-y-2">
                      <label className="block text-[10px] font-semibold">Model name<input value={customDeviceName} onChange={(event) => setCustomDeviceName(event.target.value)} className="mt-1 w-full px-2 py-1.5 rounded border border-brand-border bg-brand-bg text-xs" placeholder="e.g. Catalyst 9300-48P" /></label>
                      <label className="block text-[10px] font-semibold">Device category<select value={customDeviceCategory} onChange={(event) => setCustomDeviceCategory(event.target.value as CiscoDeviceCategory)} className="mt-1 w-full px-2 py-1.5 rounded border border-brand-border bg-brand-bg text-xs">
                        <option value="routers">Router / L3 infrastructure</option><option value="switches">Switch / bridge</option><option value="hubs">Hub / repeater</option><option value="wireless">Wireless / gateway</option><option value="security">Firewall / security</option><option value="wan">WAN / modem</option><option value="end_devices">End device / host</option>
                      </select></label>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="text-[10px] font-semibold">Ports<input type="number" min={1} max={48} value={customPortCount} onChange={(event) => setCustomPortCount(Math.max(1, Math.min(48, Number(event.target.value) || 1)))} className="mt-1 w-full px-2 py-1.5 rounded border border-brand-border bg-brand-bg text-xs" /></label>
                        <label className="text-[10px] font-semibold">Port speed<select value={customPortSpeed} onChange={(event) => setCustomPortSpeed(Number(event.target.value))} className="mt-1 w-full px-2 py-1.5 rounded border border-brand-border bg-brand-bg text-xs"><option value={100}>100 Mbps</option><option value={1000}>1 Gbps</option><option value={10000}>10 Gbps</option></select></label>
                      </div>
                      <p className="text-[10px] text-brand-text-muted">Custom models use the selected category as their simulator role; this app does not emulate Cisco CLI, IOS, VLAN configuration, or hardware firmware.</p>
                      <button onClick={handleAddCustomDevice} disabled={!customDeviceName.trim()} className="w-full px-2 py-1.5 rounded bg-brand-primary text-white text-xs font-semibold disabled:opacity-50">Add custom device</button>
                    </div>}
                    {filteredHardware.map((item) => (
                      <div
                        key={item.type}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData('text/plain', item.type);
                        }}
                        className="p-2 bg-brand-bg border border-brand-border hover:border-brand-primary/60 rounded-lg transition-all shadow-sm group cursor-grab active:cursor-grabbing"
                        title="Click to add or drag directly onto the canvas"
                      >
                        <div className="flex items-center gap-2.5">
                          <div className="w-10 h-10 rounded-md bg-brand-surface border border-brand-border flex items-center justify-center p-0.5 shrink-0 group-hover:scale-105 transition-transform">
                            <CiscoDeviceGlyph shape={item.iconShape} size={32} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-bold text-xs text-brand-text-primary truncate">
                                {item.shortName}
                              </span>
                              <span className="text-[9px] font-mono font-semibold px-1 py-0.2 rounded bg-brand-surface border border-brand-border text-brand-text-muted">
                                {item.badge}
                              </span>
                            </div>
                            <p className="text-[10px] text-brand-text-muted truncate">
                              {item.name}
                            </p>
                          </div>
                          <button
                            onClick={() => handleAddCiscoDevice(item)}
                            className="p-1 rounded bg-brand-surface hover:bg-brand-primary hover:text-white border border-brand-border text-brand-text-secondary transition-colors"
                            title={`Add ${item.shortName} to Canvas`}
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}

                    {filteredHardware.length === 0 && (
                      <div className="text-center py-6 text-brand-text-muted text-caption">
                        No devices matching &quot;{searchQuery}&quot;.
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Quick Helper Note */}
              <div className="p-2 bg-brand-bg border-t border-brand-border text-[10px] text-brand-text-muted flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-brand-primary shrink-0" />
                <span>Tip: Drag any device directly from shelf onto canvas!</span>
              </div>
            </div>
          </aside>
        )}

        {/* Draggable Resizer Splitter for Left Shelf */}
        {leftShelfOpen && (
          <div
            onPointerDown={handleStartResizeLeft}
            className={`w-2 hover:w-2.5 bg-transparent hover:bg-brand-primary active:bg-brand-primary cursor-col-resize transition-all shrink-0 z-20 flex items-center justify-center group relative select-none ${
              isResizingLeft ? 'bg-brand-primary w-2.5' : ''
            }`}
            title="Drag horizontally to resize Cisco Shelf"
          >
            <div className="w-[1.5px] h-full bg-brand-border group-hover:bg-brand-primary group-active:bg-brand-primary" />
            <div className="absolute top-1/2 -translate-y-1/2 w-4 h-9 bg-brand-surface border border-brand-border rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 group-active:opacity-100 shadow-md transition-opacity pointer-events-none">
              <GripVertical className="w-3 h-3 text-brand-primary" />
            </div>
          </div>
        )}

        {/* Center Canvas Workspace: MAXIMIZED Breathing Room */}
        <main className="flex-1 h-full min-w-0 relative overflow-hidden flex flex-col p-2">
          {showListView ? (
            <div className="w-full max-w-4xl mx-auto overflow-y-auto max-h-full p-4">
              <TopologyListView
                topology={topology}
                editable={true}
                onDeleteNode={handleDeleteNode}
                onDeleteLink={handleDeleteLink}
              />
            </div>
          ) : (
            <div className="w-full h-full flex-1 min-w-0">
              <TopologyDiagram
                topology={topology}
                selectedNodeId={selectedNode?.id}
                selectedLinkId={selectedLink?.id}
                onSelectNode={(node) => {
                  setSelectedNode(node);
                  setSelectedLink(null);
                  setRightInspectorOpen(true);
                  setActiveInspectorTab('properties');
                }}
                onSelectLink={(link) => {
                  setSelectedLink(link);
                  setSelectedNode(null);
                  setRightInspectorOpen(true);
                  setActiveInspectorTab('properties');
                }}
                onUpdateNodePosition={handleUpdateNodePosition}
                onAddLink={handleAddLink}
                onDeleteNode={handleDeleteNode}
                onDeleteLink={handleDeleteLink}
                onDuplicateNode={handleDuplicateNode}
                onDropDevice={handleDropDevice}
                activeCableType={activeCableType}
                connectingSourceId={connectingSourceId}
                onSetConnectingSourceId={setConnectingSourceId}
                gridSnap={gridSnap}
              />
            </div>
          )}
        </main>

        {/* Draggable Resizer Splitter for Right Inspector */}
        {rightInspectorOpen && (
          <div
            onPointerDown={handleStartResizeRight}
            className={`w-2 hover:w-2.5 bg-transparent hover:bg-brand-primary active:bg-brand-primary cursor-col-resize transition-all shrink-0 z-20 flex items-center justify-center group relative select-none ${
              isResizingRight ? 'bg-brand-primary w-2.5' : ''
            }`}
            title="Drag horizontally to resize Inspector"
          >
            <div className="w-[1.5px] h-full bg-brand-border group-hover:bg-brand-primary group-active:bg-brand-primary" />
            <div className="absolute top-1/2 -translate-y-1/2 w-4 h-9 bg-brand-surface border border-brand-border rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 group-active:opacity-100 shadow-md transition-opacity pointer-events-none">
              <GripVertical className="w-3 h-3 text-brand-primary" />
            </div>
          </div>
        )}

        {/* Right Inspector Panel: Collapsible, Resizable & Smooth */}
        {rightInspectorOpen && (
          <aside
            style={{ width: `${rightInspectorWidth}px` }}
            className="bg-brand-surface border-l border-brand-border flex flex-col justify-between shrink-0 shadow-md z-10 select-none"
          >
            <div className="flex flex-col h-full">
              {/* Inspector Header with Close Button */}
              <div className="flex items-center justify-between border-b border-brand-border px-3 py-2 text-caption font-semibold">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setActiveInspectorTab('properties')}
                    className={`px-2 py-1 rounded text-xs transition-colors ${
                      activeInspectorTab === 'properties'
                        ? 'bg-brand-primary text-white font-bold'
                        : 'text-brand-text-secondary hover:text-brand-text-primary'
                    }`}
                  >
                    Inspector
                  </button>
                  <button
                    onClick={() => setActiveInspectorTab('validation')}
                    className={`px-2 py-1 rounded text-xs transition-colors ${
                      activeInspectorTab === 'validation'
                        ? 'bg-brand-primary text-white font-bold'
                        : 'text-brand-text-secondary hover:text-brand-text-primary'
                    }`}
                  >
                    Validation ({errors.length})
                  </button>
                  <button
                    onClick={() => setActiveInspectorTab('summary')}
                    className={`px-2 py-1 rounded text-xs transition-colors ${
                      activeInspectorTab === 'summary'
                        ? 'bg-brand-primary text-white font-bold'
                        : 'text-brand-text-secondary hover:text-brand-text-primary'
                    }`}
                  >
                    Summary
                  </button>
                </div>

                <button
                  onClick={() => setRightInspectorOpen(false)}
                  className="p-1 text-brand-text-muted hover:text-brand-text-primary rounded"
                  title="Close Inspector"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Inspector Content */}
              <div className="p-3 flex-1 overflow-y-auto space-y-3.5">
                {activeInspectorTab === 'properties' && (
                  <div>
                    {selectedNode ? (
                      <div className="space-y-3">
                        {/* Selected Node Card */}
                        {(() => {
                          const hw = getHardwareDefinition(selectedNode.type, selectedNode.category);
                          return (
                            <div className="p-2.5 bg-brand-bg border border-brand-border rounded-xl flex items-center gap-3">
                              <div className="w-10 h-10 rounded-lg bg-brand-surface border border-brand-border flex items-center justify-center p-1 shrink-0">
                                <CiscoDeviceGlyph shape={hw.iconShape} size={36} isSelected={true} />
                              </div>
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center justify-between">
                                  <span className="font-mono text-xs font-bold text-brand-text-primary truncate">
                                    {selectedNode.id}
                                  </span>
                                  <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-brand-primary/10 text-brand-primary font-bold">
                                    {hw.badge}
                                  </span>
                                </div>
                                <p className="text-[10px] text-brand-text-muted truncate">{hw.name}</p>
                              </div>
                            </div>
                          );
                        })()}

                        {/* Label Editor */}
                        <div>
                          <label className="text-[11px] font-semibold text-brand-text-primary block mb-1">
                            Hostname / Label
                          </label>
                          <input
                            type="text"
                            value={selectedNode.label}
                            onChange={(e) => {
                              const updated = topology.nodes.map((n) =>
                                n.id === selectedNode.id ? { ...n, label: e.target.value } : n
                              );
                              setTopology({ ...topology, nodes: updated });
                              setSelectedNode({ ...selectedNode, label: e.target.value });
                            }}
                            className="w-full px-2.5 py-1.5 bg-brand-bg border border-brand-border rounded-lg text-xs text-brand-text-primary focus:outline-none focus:border-brand-primary"
                          />
                        </div>

                        {/* IP Stack */}
                        <div className="p-2.5 bg-brand-bg border border-brand-border rounded-xl space-y-2">
                          <span className="text-[10px] uppercase font-bold text-brand-text-muted tracking-wider block">
                            IP Address &amp; Subnet
                          </span>
                          <div>
                            <label className="text-[10px] text-brand-text-secondary block mb-0.5">
                              IP Address
                            </label>
                            <input
                              type="text"
                              value={selectedNode.ip || '192.168.1.10'}
                              onChange={(e) => {
                                const updated = topology.nodes.map((n) =>
                                  n.id === selectedNode.id ? { ...n, ip: e.target.value } : n
                                );
                                setTopology({ ...topology, nodes: updated });
                                setSelectedNode({ ...selectedNode, ip: e.target.value });
                              }}
                              className="w-full px-2 py-1 bg-brand-surface border border-brand-border rounded text-xs font-mono"
                            />
                          </div>
                          <div className="grid grid-cols-2 gap-2">
                            <div>
                              <label className="text-[10px] text-brand-text-secondary block mb-0.5">
                                Subnet Mask
                              </label>
                              <input
                                type="text"
                                value={selectedNode.subnet || '255.255.255.0'}
                                onChange={(e) => {
                                  const updated = topology.nodes.map((n) =>
                                    n.id === selectedNode.id ? { ...n, subnet: e.target.value } : n
                                  );
                                  setTopology({ ...topology, nodes: updated });
                                  setSelectedNode({ ...selectedNode, subnet: e.target.value });
                                }}
                                className="w-full px-2 py-1 bg-brand-surface border border-brand-border rounded text-xs font-mono"
                              />
                            </div>
                            <div>
                              <label className="text-[10px] text-brand-text-secondary block mb-0.5">
                                Gateway
                              </label>
                              <input
                                type="text"
                                value={selectedNode.gateway || '192.168.1.1'}
                                onChange={(e) => {
                                  const updated = topology.nodes.map((n) =>
                                    n.id === selectedNode.id ? { ...n, gateway: e.target.value } : n
                                  );
                                  setTopology({ ...topology, nodes: updated });
                                  setSelectedNode({ ...selectedNode, gateway: e.target.value });
                                }}
                                className="w-full px-2 py-1 bg-brand-surface border border-brand-border rounded text-xs font-mono"
                              />
                            </div>
                          </div>
                        </div>

                        {/* Interfaces List */}
                        <div>
                          <div className="flex items-center justify-between mb-1.5">
                            <label className="text-[11px] font-semibold text-brand-text-primary">
                              Cisco Interfaces
                            </label>
                            <span className="text-[9px] text-brand-text-muted font-mono">
                              {selectedNode.interfaces?.length || getHardwareDefinition(selectedNode.type, selectedNode.category).defaultPorts.length} Ports
                            </span>
                          </div>
                          <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                            {(selectedNode.interfaces || getHardwareDefinition(selectedNode.type, selectedNode.category).defaultPorts.map((p, i) => ({
                              id: `${selectedNode.id}_${i}`,
                              name: p,
                              speedMbps: 1000,
                              isUp: true,
                            }))).map((port, idx) => {
                              const isConnected = topology.links.some(
                                (l) => l.src === selectedNode.id || l.dst === selectedNode.id
                              );
                              return (
                                <div
                                  key={idx}
                                  className="p-1.5 bg-brand-bg border border-brand-border rounded-md flex items-center justify-between text-[10px]"
                                >
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className={`w-2 h-2 rounded-full ${
                                        isConnected ? 'bg-emerald-500' : 'bg-brand-text-muted/40'
                                      }`}
                                    />
                                    <span className="font-mono font-semibold text-brand-text-primary">
                                      {port.name}
                                    </span>
                                  </div>
                                  <span className="font-mono text-brand-text-muted text-[9px]">
                                    {port.speedMbps}M
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Action Buttons */}
                        <button
                          onClick={() => setConnectingSourceId(selectedNode.id)}
                          className="w-full py-1.5 bg-brand-primary text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 shadow-sm hover:opacity-90"
                        >
                          <Link2 className="w-3.5 h-3.5" />
                          <span>Draw Cable from {selectedNode.id}</span>
                        </button>

                        <div className="grid grid-cols-2 gap-2 pt-1 border-t border-brand-border">
                          <button
                            onClick={() => handleDuplicateNode(selectedNode)}
                            className="py-1.5 bg-brand-bg border border-brand-border hover:bg-brand-surface text-brand-text-primary rounded-lg text-xs font-semibold flex items-center justify-center gap-1"
                          >
                            <Copy className="w-3 h-3 text-emerald-600" />
                            <span>Duplicate</span>
                          </button>
                          <button
                            onClick={() => handleDeleteNode(selectedNode.id)}
                            className="py-1.5 border border-rose-300 dark:border-rose-800 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg text-xs font-semibold flex items-center justify-center gap-1"
                          >
                            <Trash2 className="w-3 h-3" />
                            <span>Delete</span>
                          </button>
                        </div>
                      </div>
                    ) : selectedLink ? (
                      <div className="space-y-3">
                        <div className="flex items-center justify-between pb-1.5 border-b border-brand-border">
                          <span className="text-overline text-brand-text-muted">Physical Cable</span>
                          <span className="font-mono text-xs font-bold text-brand-text-primary">
                            {selectedLink.src} ↔ {selectedLink.dst}
                          </span>
                        </div>

                        {/* Cable Media Type */}
                        <div>
                          <label className="text-[11px] font-semibold text-brand-text-primary block mb-1">
                            Media Standard
                          </label>
                          <select
                            value={selectedLink.cableType || 'copper_straight'}
                            onChange={(e) => {
                              const requestedType = e.target.value as CableType;
                              const source = topology.nodes.find((node) => node.id === selectedLink.src);
                              const destination = topology.nodes.find((node) => node.id === selectedLink.dst);
                              const newType = requestedType === 'auto'
                                ? (source && destination ? inferCableType(source, destination) : 'copper_straight')
                                : requestedType;
                              const cableDef = CISCO_CABLES.find((c) => c.type === newType);
                              const updated = topology.links.map((l) =>
                                l.id === selectedLink.id
                                  ? {
                                      ...l,
                                      cableType: newType,
                                      ...(cableDef?.simulationSupported === false ? { simulationIncluded: false } : { simulationIncluded: true }),
                                      bandwidth_mbps: cableDef ? cableDef.defaultSpeed : l.bandwidth_mbps,
                                    }
                                  : l
                              );
                              commitTopology({ ...topology, links: updated }, 'Changed cable media');
                              setSelectedLink({
                                ...selectedLink,
                                cableType: newType,
                                simulationIncluded: cableDef?.simulationSupported !== false,
                                bandwidth_mbps: cableDef ? cableDef.defaultSpeed : selectedLink.bandwidth_mbps,
                              });
                            }}
                            className="w-full px-2.5 py-1.5 bg-brand-bg border border-brand-border rounded-lg text-xs font-medium"
                          >
                            {CISCO_CABLES.map((c) => (
                              <option key={c.type} value={c.type}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        </div>

                        {/* Bandwidth Throughput */}
                        <div>
                          <label className="text-[11px] font-semibold text-brand-text-primary block mb-1">
                            Throughput (Mbps)
                          </label>
                          <div className="grid grid-cols-4 gap-1 mb-1.5">
                            {[100, 500, 1000, 10000].map((bw) => (
                              <button
                                key={bw}
                                onClick={() => {
                                  const updated = topology.links.map((l) =>
                                    l.id === selectedLink.id ? { ...l, bandwidth_mbps: bw } : l
                                  );
                                  commitTopology({ ...topology, links: updated });
                                  setSelectedLink({ ...selectedLink, bandwidth_mbps: bw });
                                }}
                                className={`py-1 rounded text-[10px] font-mono font-semibold border ${
                                  selectedLink.bandwidth_mbps === bw
                                    ? 'bg-brand-primary text-white border-brand-primary'
                                    : 'bg-brand-bg border-brand-border text-brand-text-secondary hover:border-brand-primary'
                                }`}
                              >
                                {bw >= 1000 ? `${bw / 1000}G` : `${bw}M`}
                              </button>
                            ))}
                          </div>
                          <input
                            type="number"
                            value={selectedLink.bandwidth_mbps}
                            onChange={(e) => {
                              const val = Number(e.target.value);
                              const updated = topology.links.map((l) =>
                                l.id === selectedLink.id ? { ...l, bandwidth_mbps: val } : l
                              );
                              setTopology({ ...topology, links: updated });
                              setSelectedLink({ ...selectedLink, bandwidth_mbps: val });
                            }}
                            className="w-full px-2 py-1 bg-brand-bg border border-brand-border rounded text-xs font-mono"
                          />
                        </div>

                        {/* Latency & Loss */}
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] text-brand-text-primary block mb-0.5">Latency (ms)</label>
                            <input
                              type="number"
                              step="0.5"
                              value={selectedLink.latency_ms}
                              onChange={(e) => {
                                const val = Number(e.target.value);
                                const updated = topology.links.map((l) =>
                                  l.id === selectedLink.id ? { ...l, latency_ms: val } : l
                                );
                                setTopology({ ...topology, links: updated });
                                setSelectedLink({ ...selectedLink, latency_ms: val });
                              }}
                              className="w-full px-2 py-1 bg-brand-bg border border-brand-border rounded text-xs font-mono"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] text-brand-text-primary block mb-0.5">Loss (%)</label>
                            <input
                              type="number"
                              min="0"
                              max="100"
                              value={selectedLink.loss_percent}
                              onChange={(e) => {
                                const val = Number(e.target.value);
                                const updated = topology.links.map((l) =>
                                  l.id === selectedLink.id ? { ...l, loss_percent: val } : l
                                );
                                setTopology({ ...topology, links: updated });
                                setSelectedLink({ ...selectedLink, loss_percent: val });
                              }}
                              className="w-full px-2 py-1 bg-brand-bg border border-brand-border rounded text-xs font-mono"
                            />
                          </div>
                        </div>

                        {/* Disconnect Cable Button */}
                        <button
                          onClick={() => handleDeleteLink(selectedLink.id)}
                          className="w-full py-1.5 rounded-lg border border-rose-300 dark:border-rose-800 text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-xs font-semibold flex items-center justify-center gap-1 mt-2"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                          <span>Disconnect Cable</span>
                        </button>
                      </div>
                    ) : (
                      <div className="text-center py-8 px-2 text-brand-text-muted space-y-2">
                        <Sliders className="w-8 h-8 mx-auto text-brand-text-muted/60" />
                        <p className="text-xs font-semibold text-brand-text-primary">
                          Select a Device or Cable
                        </p>
                        <p className="text-[11px]">
                          Click any router, switch, PC, or wire on the canvas to inspect its ports and parameters.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {activeInspectorTab === 'validation' && (
                  <div className="space-y-3">
                    {errors.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="text-[11px] text-rose-600 font-bold flex items-center gap-1">
                          <AlertTriangle className="w-3.5 h-3.5" />
                          <span>Blockers ({errors.length})</span>
                        </span>
                        {errors.map((err, i) => (
                          <div
                            key={i}
                            className="p-2 bg-rose-50 dark:bg-rose-950/40 border border-rose-300 dark:border-rose-800 rounded text-[11px] text-rose-900 dark:text-rose-200"
                          >
                            {err}
                          </div>
                        ))}
                      </div>
                    )}

                    {warnings.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="text-[11px] text-amber-600 font-bold flex items-center gap-1">
                          <Info className="w-3.5 h-3.5" />
                          <span>Warnings ({warnings.length})</span>
                        </span>
                        {warnings.map((w, i) => (
                          <div
                            key={i}
                            className="p-2 bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 rounded text-[11px] text-amber-900 dark:text-amber-200"
                          >
                            {w}
                          </div>
                        ))}
                      </div>
                    )}

                    {errors.length === 0 && (
                      <div className="p-3 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 rounded-lg text-emerald-900 dark:text-emerald-200 text-xs">
                        <span className="font-bold block flex items-center gap-1.5">
                          <CheckCircle className="w-4 h-4 text-emerald-600" />
                          <span>Valid for Simulation</span>
                        </span>
                        <p className="text-[11px] mt-1">
                          {routerCount} routing forwarders and {hostCount} host endpoints ready.
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {activeInspectorTab === 'summary' && (
                  <div className="space-y-2 text-xs text-brand-text-secondary">
                    <div className="flex justify-between py-1 border-b border-brand-border">
                      <span>Routing Forwarders</span>
                      <span className="font-mono font-bold text-brand-text-primary">{routerCount}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-brand-border">
                      <span>Host Leaf Endpoints</span>
                      <span className="font-mono font-bold text-brand-text-primary">{hostCount}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-brand-border">
                      <span>Active Cables</span>
                      <span className="font-mono font-bold text-brand-text-primary">{topology.links.length}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
};
