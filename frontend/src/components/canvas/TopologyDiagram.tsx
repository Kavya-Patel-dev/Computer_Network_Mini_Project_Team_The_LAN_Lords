import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Topology, NetworkNode, NetworkLink, CableType, NodeType } from '../../types/network';
import { getHardwareDefinition, CISCO_CABLES } from '../../mock/ciscoHardware';
import { CiscoDeviceGlyph, GlyphShape } from './CiscoDeviceGlyph';
import { 
  ZoomIn, 
  ZoomOut, 
  Maximize2, 
  RotateCcw, 
  Trash2, 
  Copy, 
  Link2, 
  Sliders, 
  Pin, 
  X,
  Move,
  MousePointer,
  HelpCircle
} from 'lucide-react';

interface TopologyDiagramProps {
  topology: Topology;
  selectedNodeId?: string;
  selectedLinkId?: string;
  onSelectNode?: (node: NetworkNode) => void;
  onSelectLink?: (link: NetworkLink) => void;
  onUpdateNodePosition?: (nodeId: string, x: number, y: number) => void;
  onAddLink?: (src: string, dst: string, cableType: CableType) => void;
  onDeleteNode?: (nodeId: string) => void;
  onDeleteLink?: (linkId: string) => void;
  onDuplicateNode?: (node: NetworkNode) => void;
  onDropDevice?: (type: NodeType, x: number, y: number) => void;
  activeCableType?: CableType;
  connectingSourceId?: string | null;
  onSetConnectingSourceId?: (nodeId: string | null) => void;
  gridSnap?: boolean;
  heatValues?: Record<string, number>;
  highlightPaths?: string[][];
  failedElements?: { nodes?: string[]; links?: string[] };
  pins?: Array<{ elementId: string; note: string; author: string }>;
  interactive?: boolean;
  className?: string;
  showLabels?: boolean;
}

interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  targetType: 'node' | 'link' | 'canvas';
  node?: NetworkNode;
  link?: NetworkLink;
}

export const TopologyDiagram: React.FC<TopologyDiagramProps> = ({
  topology,
  selectedNodeId,
  selectedLinkId,
  onSelectNode,
  onSelectLink,
  onUpdateNodePosition,
  onAddLink,
  onDeleteNode,
  onDeleteLink,
  onDuplicateNode,
  onDropDevice,
  activeCableType = 'copper_straight',
  connectingSourceId: externalConnectingSourceId,
  onSetConnectingSourceId,
  gridSnap = true,
  heatValues,
  highlightPaths = [],
  failedElements = {},
  pins = [],
  interactive = true,
  className = '',
  showLabels = true,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState<number>(0.9);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 40, y: 30 });
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Mode: select vs pan
  const [canvasMode, setCanvasMode] = useState<'select' | 'pan'>('select');

  // Node Dragging state
  const [draggedNodeId, setDraggedNodeId] = useState<string | null>(null);
  const dragOffsetRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragCurrentPos, setDragCurrentPos] = useState<{ x: number; y: number } | null>(null);

  // Cable Connection drawing state
  const [internalConnectingId, setInternalConnectingId] = useState<string | null>(null);
  const connectingSourceId = externalConnectingSourceId !== undefined ? externalConnectingSourceId : internalConnectingId;
  const setConnectingSource = (id: string | null) => {
    if (onSetConnectingSourceId) onSetConnectingSourceId(id);
    else setInternalConnectingId(id);
  };

  const [mouseCoord, setMouseCoord] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [showHelpHint, setShowHelpHint] = useState(false);

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    isOpen: false,
    x: 0,
    y: 0,
    targetType: 'canvas',
  });

  // Hover states
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredLink, setHoveredLink] = useState<string | null>(null);

  // Convert screen coordinates to SVG internal coordinate space
  const screenToSvgCoordinates = useCallback(
    (clientX: number, clientY: number) => {
      if (!svgRef.current) return { x: clientX, y: clientY };
      const svg = svgRef.current;
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      const ctm = svg.getScreenCTM();
      if (!ctm) return { x: clientX, y: clientY };
      const local = pt.matrixTransform(ctm.inverse());
      return {
        x: (local.x - pan.x) / zoom,
        y: (local.y - pan.y) / zoom,
      };
    },
    [pan, zoom]
  );

  // Auto-fit on initial render
  const handleFitToScreen = useCallback(() => {
    if (topology.nodes.length === 0) {
      setZoom(1);
      setPan({ x: 40, y: 40 });
      return;
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    topology.nodes.forEach((n) => {
      const nx = n.x ?? 100;
      const ny = n.y ?? 100;
      if (nx < minX) minX = nx;
      if (nx > maxX) maxX = nx;
      if (ny < minY) minY = ny;
      if (ny > maxY) maxY = ny;
    });

    const padding = 100;
    const boundsWidth = Math.max(maxX - minX + padding * 2, 600);
    const boundsHeight = Math.max(maxY - minY + padding * 2, 450);

    const containerWidth = containerRef.current?.clientWidth || 900;
    const containerHeight = containerRef.current?.clientHeight || 600;

    const scaleX = containerWidth / boundsWidth;
    const scaleY = containerHeight / boundsHeight;
    const optimalScale = Math.min(scaleX, scaleY, 1.2);
    // Large imported/generated graphs can need less than 45% zoom to fit.
    // The old floor made Fit leave parts of the topology clipped.
    const clampedScale = Math.max(0.15, Math.min(optimalScale, 1.2));

    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;

    setZoom(Number(clampedScale.toFixed(2)));
    setPan({
      x: containerWidth / 2 - centerX * clampedScale,
      y: containerHeight / 2 - centerY * clampedScale,
    });
  }, [topology.nodes]);

  // Initial centering on mount
  useEffect(() => {
    const timer = setTimeout(() => {
      handleFitToScreen();
    }, 150);
    return () => clearTimeout(timer);
  }, []);

  // Close context menu on outside click or escape
  useEffect(() => {
    const handleGlobalClick = () => {
      if (contextMenu.isOpen) {
        setContextMenu((prev) => ({ ...prev, isOpen: false }));
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConnectingSource(null);
        setContextMenu((prev) => ({ ...prev, isOpen: false }));
      }
      if (e.code === 'Space' && (e.target as HTMLElement).tagName !== 'INPUT') {
        setCanvasMode((prev) => (prev === 'pan' ? 'select' : 'pan'));
      }
    };
    window.addEventListener('click', handleGlobalClick);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('click', handleGlobalClick);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [contextMenu.isOpen]);

  // Global window listeners for drag & pan to prevent getting stuck
  useEffect(() => {
    if (!isPanning && !draggedNodeId) return;

    const handleWindowPointerMove = (e: PointerEvent) => {
      if (isPanning) {
        setPan({
          x: e.clientX - panStartRef.current.x,
          y: e.clientY - panStartRef.current.y,
        });
        return;
      }

      if (draggedNodeId) {
        const local = screenToSvgCoordinates(e.clientX, e.clientY);
        let nextX = local.x - dragOffsetRef.current.x;
        let nextY = local.y - dragOffsetRef.current.y;

        if (gridSnap) {
          nextX = Math.round(nextX / 20) * 20;
          nextY = Math.round(nextY / 20) * 20;
        }

        nextX = Math.max(40, Math.min(2400, nextX));
        nextY = Math.max(40, Math.min(1800, nextY));

        setDragCurrentPos({ x: nextX, y: nextY });
      }
    };

    const handleWindowPointerUp = () => {
      if (isPanning) {
        setIsPanning(false);
      }
      if (draggedNodeId && dragCurrentPos) {
        if (onUpdateNodePosition) {
          onUpdateNodePosition(draggedNodeId, dragCurrentPos.x, dragCurrentPos.y);
        }
        setDraggedNodeId(null);
        setDragCurrentPos(null);
      } else if (draggedNodeId) {
        setDraggedNodeId(null);
      }
    };

    window.addEventListener('pointermove', handleWindowPointerMove);
    window.addEventListener('pointerup', handleWindowPointerUp);
    return () => {
      window.removeEventListener('pointermove', handleWindowPointerMove);
      window.removeEventListener('pointerup', handleWindowPointerUp);
    };
  }, [isPanning, draggedNodeId, dragCurrentPos, gridSnap, onUpdateNodePosition, screenToSvgCoordinates]);

  // Link appearance
  const getLinkAppearance = (link: NetworkLink) => {
    const isFailed = failedElements.links?.includes(link.id);
    const cableDef = CISCO_CABLES.find((c) => c.type === link.cableType) || CISCO_CABLES[0];

    let color = cableDef.color;
    let dash = cableDef.strokeDash;

    if (isFailed) {
      color = '#EF4444';
      dash = '6,6';
    } else if (heatValues && heatValues[link.id] !== undefined) {
      const val = heatValues[link.id];
      if (val < 50) color = '#10B981';
      else if (val < 80) color = '#F59E0B';
      else if (val <= 100) color = '#EA580C';
      else color = '#DC2626';
    }

    return { color, dash, cableDef };
  };

  // Node helper
  const getNode = (id: string) => {
    const found = topology.nodes.find((n) => n.id === id);
    if (!found) return undefined;
    if (draggedNodeId === id && dragCurrentPos) {
      return { ...found, x: dragCurrentPos.x, y: dragCurrentPos.y };
    }
    return found;
  };

  // Zoom controls
  const handleZoom = (delta: number) => {
    setZoom((prev) => Math.min(Math.max(0.15, Number((prev + delta).toFixed(2))), 2.5));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 60, y: 40 });
  };

  // Background pointer down (Pan or cancel connecting)
  const handleSvgPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if (e.button !== 0 && e.button !== 1) return;
    if (!interactive) return;

    // Check if target is background
    const target = e.target as HTMLElement;
    if (
      target.tagName === 'svg' ||
      target.getAttribute('data-canvas-bg') === 'true' ||
      canvasMode === 'pan' ||
      e.button === 1
    ) {
      setIsPanning(true);
      panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
      if (connectingSourceId) {
        setConnectingSource(null);
      }
    }
  };

  // Node pointer down (Drag Start or Link Target)
  const handleNodePointerDown = (e: React.PointerEvent, node: NetworkNode) => {
    e.stopPropagation();
    if (!interactive) return;

    if (e.button === 0) {
      // If currently connecting a cable, clicking this node completes the link!
      if (connectingSourceId) {
        if (connectingSourceId !== node.id) {
          if (onAddLink) {
            onAddLink(connectingSourceId, node.id, activeCableType);
          }
        }
        setConnectingSource(null);
        return;
      }

      if (canvasMode === 'pan') {
        setIsPanning(true);
        panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
        return;
      }

      // Initiate dragging
      const local = screenToSvgCoordinates(e.clientX, e.clientY);
      const nx = node.x ?? 100;
      const ny = node.y ?? 100;
      dragOffsetRef.current = { x: local.x - nx, y: local.y - ny };
      setDraggedNodeId(node.id);
      setDragCurrentPos({ x: nx, y: ny });

      if (onSelectNode) onSelectNode(node);
    }
  };

  // Local Pointer Move on SVG (for wire drawing & hover coords)
  const handleSvgPointerMove = (e: React.PointerEvent) => {
    if (!interactive) return;
    const local = screenToSvgCoordinates(e.clientX, e.clientY);
    setMouseCoord(local);
  };

  // Smooth wheel zoom centered on cursor
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (!interactive) return;

    const rect = containerRef.current?.getBoundingClientRect();
    const mouseX = e.clientX - (rect?.left || 0);
    const mouseY = e.clientY - (rect?.top || 0);

    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.88;
    const nextZoom = Math.min(Math.max(0.15, Number((zoom * zoomFactor).toFixed(3))), 2.5);

    // Adjust pan so the position under cursor remains stable
    const nextPanX = mouseX - (mouseX - pan.x) * (nextZoom / zoom);
    const nextPanY = mouseY - (mouseY - pan.y) * (nextZoom / zoom);

    setZoom(Number(nextZoom.toFixed(2)));
    setPan({ x: nextPanX, y: nextPanY });
  };

  // HTML5 Drag-and-drop from device shelf directly onto canvas
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const deviceType = e.dataTransfer.getData('text/plain') as NodeType;
    if (deviceType && onDropDevice) {
      const local = screenToSvgCoordinates(e.clientX, e.clientY);
      let dropX = Math.round(local.x);
      let dropY = Math.round(local.y);
      if (gridSnap) {
        dropX = Math.round(dropX / 20) * 20;
        dropY = Math.round(dropY / 20) * 20;
      }
      onDropDevice(deviceType, dropX, dropY);
    }
  };

  // Right-click context menus
  const handleNodeContextMenu = (e: React.MouseEvent, node: NetworkNode) => {
    e.preventDefault();
    e.stopPropagation();
    if (!interactive) return;

    const rect = containerRef.current?.getBoundingClientRect();
    const x = e.clientX - (rect?.left || 0);
    const y = e.clientY - (rect?.top || 0);

    setContextMenu({
      isOpen: true,
      x: Math.min(x, (rect?.width || 800) - 200),
      y: Math.min(y, (rect?.height || 500) - 170),
      targetType: 'node',
      node,
    });
    if (onSelectNode) onSelectNode(node);
  };

  const handleLinkContextMenu = (e: React.MouseEvent, link: NetworkLink) => {
    e.preventDefault();
    e.stopPropagation();
    if (!interactive) return;

    const rect = containerRef.current?.getBoundingClientRect();
    const x = e.clientX - (rect?.left || 0);
    const y = e.clientY - (rect?.top || 0);

    setContextMenu({
      isOpen: true,
      x: Math.min(x, (rect?.width || 800) - 200),
      y: Math.min(y, (rect?.height || 500) - 130),
      targetType: 'link',
      link,
    });
    if (onSelectLink) onSelectLink(link);
  };

  const handleCanvasContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!interactive) return;

    const rect = containerRef.current?.getBoundingClientRect();
    const x = e.clientX - (rect?.left || 0);
    const y = e.clientY - (rect?.top || 0);

    setContextMenu({
      isOpen: true,
      x: Math.min(x, (rect?.width || 800) - 200),
      y: Math.min(y, (rect?.height || 500) - 130),
      targetType: 'canvas',
    });
  };

  const connectingSrcNode = connectingSourceId ? getNode(connectingSourceId) : null;

  return (
    <div
      ref={containerRef}
      onWheel={handleWheel}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      className={`relative w-full h-full min-h-[560px] bg-brand-surface border border-brand-border rounded-xl overflow-hidden select-none touch-none shadow-inner ${className}`}
      style={{
        cursor: isPanning ? 'grabbing' : canvasMode === 'pan' ? 'grab' : connectingSourceId ? 'crosshair' : 'default',
      }}
    >
      {/* Floating Canvas Navigation Toolbar */}
      <div className="absolute top-3 right-3 z-30 flex items-center gap-1.5 bg-brand-surface/95 backdrop-blur-md border border-brand-border px-2 py-1.5 rounded-xl shadow-lg">
        {/* Pointer Mode vs Pan Mode */}
        <div className="flex items-center bg-brand-bg rounded-lg p-0.5 border border-brand-border">
          <button
            onClick={() => setCanvasMode('select')}
            className={`p-1.5 rounded text-caption font-semibold flex items-center gap-1 transition-colors ${
              canvasMode === 'select'
                ? 'bg-brand-primary text-white shadow-sm'
                : 'text-brand-text-secondary hover:text-brand-text-primary'
            }`}
            title="Select & Move Mode (V)"
          >
            <MousePointer className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setCanvasMode('pan')}
            className={`p-1.5 rounded text-caption font-semibold flex items-center gap-1 transition-colors ${
              canvasMode === 'pan'
                ? 'bg-brand-primary text-white shadow-sm'
                : 'text-brand-text-secondary hover:text-brand-text-primary'
            }`}
            title="Pan Hand Tool (Space)"
          >
            <Move className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="h-5 w-[1px] bg-brand-border" />

        {/* Zoom Controls */}
        <button
          onClick={() => handleZoom(0.15)}
          className="p-1.5 text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg rounded-lg transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          onClick={() => handleZoom(-0.15)}
          className="p-1.5 text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg rounded-lg transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>

        <button
          onClick={handleResetView}
          className="px-2 py-1 text-[11px] font-mono font-bold text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg rounded-lg transition-colors"
          title="Reset Zoom to 100%"
        >
          {Math.round(zoom * 100)}%
        </button>

        <button
          onClick={handleFitToScreen}
          className="p-1.5 text-brand-text-secondary hover:text-brand-text-primary hover:bg-brand-bg rounded-lg transition-colors"
          title="Fit Topology in View"
        >
          <Maximize2 className="w-4 h-4" />
        </button>

        <div className="h-5 w-[1px] bg-brand-border" />

        {/* Help hints toggle */}
        <button
          onClick={() => setShowHelpHint(!showHelpHint)}
          className={`p-1.5 rounded-lg transition-colors ${
            showHelpHint ? 'bg-brand-primary text-white' : 'text-brand-text-muted hover:text-brand-text-primary'
          }`}
          title="Canvas Keyboard Shortcuts"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      </div>

      {/* Keyboard & Mouse Tips Overlay */}
      {showHelpHint && (
        <div className="absolute top-14 right-3 z-30 bg-brand-surface/95 backdrop-blur-md border border-brand-border p-3 rounded-xl shadow-xl text-[11px] text-brand-text-secondary space-y-1.5 w-64 animate-in fade-in zoom-in-95 duration-100">
          <div className="flex items-center justify-between font-bold text-brand-text-primary pb-1 border-b border-brand-border">
            <span>Canvas Navigation</span>
            <button onClick={() => setShowHelpHint(false)}>
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
          <p>• <b>Click &amp; Drag Device</b>: Reposition node</p>
          <p>• <b>Drag from Device Dots</b>: Draw cable</p>
          <p>• <b>Mouse Wheel</b>: Zoom centered at cursor</p>
          <p>• <b>Drag Canvas / Space</b>: Pan view</p>
          <p>• <b>Right-Click</b>: Device &amp; Cable options</p>
          <p>• <b>Ctrl+Z / Ctrl+Y</b>: Undo &amp; Redo</p>
          <p>• <b>Drag from Shelf</b>: Drop devices anywhere</p>
        </div>
      )}

      {/* Live Connecting Wire Banner */}
      {connectingSourceId && connectingSrcNode && (
        <div className="absolute top-3 left-3 z-30 flex items-center gap-2 bg-brand-primary text-white px-3.5 py-2 rounded-xl shadow-xl text-caption font-semibold animate-pulse">
          <Link2 className="w-4 h-4" />
          <span>Click any target device to connect from {connectingSrcNode.id}...</span>
          <button
            onClick={() => setConnectingSource(null)}
            className="ml-2 p-1 hover:bg-white/20 rounded-md transition-colors"
            title="Cancel Connection"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* SVG Canvas Workspace */}
      <svg
        ref={svgRef}
        onPointerDown={handleSvgPointerDown}
        onPointerMove={handleSvgPointerMove}
        onContextMenu={handleCanvasContextMenu}
        className="w-full h-full"
        style={{ width: '100%', height: '100%' }}
      >
        <defs>
          {/* Subtle Grid Pattern */}
          <pattern id="canvas-grid-lines" width="40" height="40" patternUnits="userSpaceOnUse">
            <path
              d="M 40 0 L 0 0 0 40"
              fill="none"
              stroke="currentColor"
              strokeOpacity="0.05"
              className="text-brand-text-muted"
              strokeWidth="1"
            />
          </pattern>
          {/* Dot Grid Pattern */}
          <pattern id="canvas-grid-dots" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="2" cy="2" r="1.2" fill="currentColor" fillOpacity="0.16" className="text-brand-text-muted" />
          </pattern>
        </defs>

        {/* Clickable Background for Pan */}
        <rect
          data-canvas-bg="true"
          width="100%"
          height="100%"
          fill="url(#canvas-grid-dots)"
        />

        {/* Viewport Transform Group (Pan & Zoom) */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Physical Cables / Links */}
          {topology.links.map((link) => {
            const src = getNode(link.src);
            const dst = getNode(link.dst);
            if (!src || !dst) return null;

            const x1 = src.x ?? 100;
            const y1 = src.y ?? 100;
            const x2 = dst.x ?? 200;
            const y2 = dst.y ?? 200;

            const isSelected = selectedLinkId === link.id;
            const isHovered = hoveredLink === link.id;
            const { color, dash, cableDef } = getLinkAppearance(link);

            // Highlight path check
            const isInPath = highlightPaths.some((p) => {
              for (let i = 0; i < p.length - 1; i++) {
                if (
                  (p[i] === link.src && p[i + 1] === link.dst) ||
                  (p[i] === link.dst && p[i + 1] === link.src)
                ) {
                  return true;
                }
              }
              return false;
            });

            const strokeColor = isInPath ? '#10B981' : isSelected ? '#2563EB' : color;
            const strokeWidth = isInPath ? 5.5 : isSelected ? 4.5 : isHovered ? 3.8 : 2.5;
            const midX = (x1 + x2) / 2;
            const midY = (y1 + y2) / 2;

            return (
              <g
                key={link.id}
                onClick={() => interactive && onSelectLink && onSelectLink(link)}
                onContextMenu={(e) => handleLinkContextMenu(e, link)}
                onMouseEnter={() => setHoveredLink(link.id)}
                onMouseLeave={() => setHoveredLink(null)}
                className={interactive ? 'cursor-pointer' : ''}
              >
                {/* Invisible wide hit box */}
                <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="transparent" strokeWidth="22" />

                {/* Visible Physical Cable */}
                <line
                  x1={x1}
                  y1={y1}
                  x2={x2}
                  y2={y2}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  strokeDasharray={dash}
                  strokeLinecap="round"
                />

                {/* Port End Terminals */}
                <circle cx={x1} cy={y1} r="3.5" fill={strokeColor} />
                <circle cx={x2} cy={y2} r="3.5" fill={strokeColor} />

                {/* Cable Bandwidth Badge */}
                {showLabels && (
                  <g transform={`translate(${midX}, ${midY})`}>
                    <rect
                      x="-28"
                      y="-11"
                      width="56"
                      height="22"
                      rx="6"
                      fill="var(--color-surface)"
                      stroke={isSelected ? '#2563EB' : 'var(--color-border)'}
                      strokeWidth={isSelected ? '2' : '1'}
                      className="shadow-sm"
                    />
                    <text
                      textAnchor="middle"
                      dy="4"
                      className="text-[10.5px] font-mono font-bold fill-brand-text-secondary pointer-events-none"
                    >
                      {heatValues && heatValues[link.id] !== undefined
                        ? `${heatValues[link.id]}%`
                        : `${link.bandwidth_mbps >= 1000 ? `${link.bandwidth_mbps / 1000}G` : `${link.bandwidth_mbps}M`}`}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* Live Connecting Wire following pointer */}
          {connectingSourceId && connectingSrcNode && (
            <g className="pointer-events-none">
              <line
                x1={connectingSrcNode.x ?? 100}
                y1={connectingSrcNode.y ?? 100}
                x2={mouseCoord.x}
                y2={mouseCoord.y}
                stroke="#2563EB"
                strokeWidth="2.8"
                strokeDasharray="6,4"
              />
              <circle
                cx={mouseCoord.x}
                cy={mouseCoord.y}
                r="6"
                fill="#2563EB"
                fillOpacity="0.3"
                stroke="#2563EB"
                strokeWidth="2"
              />
            </g>
          )}

          {/* Cisco Devices / Nodes */}
          {topology.nodes.map((node) => {
            const isBeingDragged = draggedNodeId === node.id;
            const x = isBeingDragged && dragCurrentPos ? dragCurrentPos.x : node.x ?? 100;
            const y = isBeingDragged && dragCurrentPos ? dragCurrentPos.y : node.y ?? 100;

            const isSelected = selectedNodeId === node.id;
            const isHovered = hoveredNode === node.id;
            const isFailed = failedElements.nodes?.includes(node.id);
            const isConnectingSource = connectingSourceId === node.id;
            const pin = pins.find((p) => p.elementId === node.id);

            const hw = getHardwareDefinition(node.type, node.category);
            const iconShape: GlyphShape = hw.iconShape;

            return (
              <g
                key={node.id}
                transform={`translate(${x}, ${y})`}
                onPointerDown={(e) => handleNodePointerDown(e, node)}
                onContextMenu={(e) => handleNodeContextMenu(e, node)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                className={interactive ? 'cursor-grab active:cursor-grabbing' : ''}
              >
                {/* Selection Halo */}
                {(isSelected || isConnectingSource) && (
                  <rect
                    x="-32"
                    y="-32"
                    width="64"
                    height="64"
                    rx="14"
                    fill="none"
                    stroke="#2563EB"
                    strokeWidth="2.5"
                    strokeDasharray={isConnectingSource ? '4,4' : undefined}
                    className={isConnectingSource ? 'animate-spin' : ''}
                  />
                )}

                {/* Node Backing Card */}
                <rect
                  x="-26"
                  y="-26"
                  width="52"
                  height="52"
                  rx="12"
                  fill="var(--color-surface)"
                  fillOpacity="0.95"
                  stroke={
                    isFailed
                      ? '#DC2626'
                      : isSelected
                      ? '#2563EB'
                      : isHovered
                      ? '#64748B'
                      : 'var(--color-border)'
                  }
                  strokeWidth={isSelected ? '2.5' : '1.2'}
                  className="shadow-md transition-colors"
                />

                {/* Authentic Cisco Device Glyph Vector */}
                <g transform="translate(-24, -24)" className="pointer-events-none">
                  <CiscoDeviceGlyph
                    shape={iconShape}
                    size={48}
                    isSelected={isSelected}
                    isFailed={isFailed}
                  />
                </g>

                {/* 4 Port Connection Handles (appear on hover/select) */}
                {interactive && (isHovered || isSelected) && !connectingSourceId && (
                  <g>
                    {/* Top port handle */}
                    <circle
                      cx="0"
                      cy="-26"
                      r="5"
                      fill="#2563EB"
                      stroke="#FFFFFF"
                      strokeWidth="1.8"
                      className="cursor-crosshair hover:scale-150 transition-transform"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConnectingSource(node.id);
                      }}
                    >
                      <title>Connect Cable from Top Port</title>
                    </circle>

                    {/* Bottom port handle */}
                    <circle
                      cx="0"
                      cy="26"
                      r="5"
                      fill="#2563EB"
                      stroke="#FFFFFF"
                      strokeWidth="1.8"
                      className="cursor-crosshair hover:scale-150 transition-transform"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConnectingSource(node.id);
                      }}
                    >
                      <title>Connect Cable from Bottom Port</title>
                    </circle>

                    {/* Right port handle */}
                    <circle
                      cx="26"
                      cy="0"
                      r="5"
                      fill="#2563EB"
                      stroke="#FFFFFF"
                      strokeWidth="1.8"
                      className="cursor-crosshair hover:scale-150 transition-transform"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConnectingSource(node.id);
                      }}
                    >
                      <title>Connect Cable from Right Port</title>
                    </circle>

                    {/* Left port handle */}
                    <circle
                      cx="-26"
                      cy="0"
                      r="5"
                      fill="#2563EB"
                      stroke="#FFFFFF"
                      strokeWidth="1.8"
                      className="cursor-crosshair hover:scale-150 transition-transform"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConnectingSource(node.id);
                      }}
                    >
                      <title>Connect Cable from Left Port</title>
                    </circle>
                  </g>
                )}

                {/* Admin Pin Annotation */}
                {pin && (
                  <g transform="translate(18, -22)">
                    <circle r="9" fill="#EA580C" stroke="#FFFFFF" strokeWidth="1.5" />
                    <foreignObject x="-5" y="-5" width="10" height="10">
                      <Pin className="w-2.5 h-2.5 text-white" />
                    </foreignObject>
                  </g>
                )}

                {/* Device Labels */}
                {showLabels && (
                  <g transform="translate(0, 38)" className="pointer-events-none">
                    <text
                      textAnchor="middle"
                      className="text-[12px] font-bold font-mono fill-brand-text-primary node-label-halo"
                    >
                      {node.id}
                    </text>
                    <text
                      textAnchor="middle"
                      dy="14"
                      className="text-[10px] font-medium fill-brand-text-secondary node-label-halo"
                    >
                      {node.label || hw.shortName}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* Floating Bottom Canvas Summary Pill */}
      <div className="absolute bottom-3 left-3 flex items-center gap-3 bg-brand-surface/90 backdrop-blur-md border border-brand-border px-3.5 py-2 rounded-xl text-caption text-brand-text-secondary shadow-md z-20">
        <div className="flex items-center gap-2 font-semibold text-brand-text-primary">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>{topology.nodes.length} Devices</span>
        </div>
        <span>•</span>
        <span>{topology.links.length} Connected Cables</span>
        {gridSnap && (
          <>
            <span>•</span>
            <span className="text-[11px] font-mono text-brand-text-muted">Snap 20px</span>
          </>
        )}
      </div>

      {/* Right-Click Context Menu */}
      {contextMenu.isOpen && (
        <div
          className="absolute z-50 bg-brand-surface border border-brand-border rounded-xl shadow-2xl py-1.5 w-56 text-caption font-medium animate-in fade-in zoom-in-95 duration-100"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={(e) => e.stopPropagation()}
        >
          {contextMenu.targetType === 'node' && contextMenu.node && (
            <>
              <div className="px-3.5 py-2 border-b border-brand-border font-mono text-[11px] font-bold text-brand-text-secondary flex items-center justify-between">
                <span>{contextMenu.node.id}</span>
                <span className="text-[10px] text-brand-text-muted uppercase">{contextMenu.node.type}</span>
              </div>
              <button
                onClick={() => {
                  setConnectingSource(contextMenu.node!.id);
                  setContextMenu((prev) => ({ ...prev, isOpen: false }));
                }}
                className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
              >
                <Link2 className="w-4 h-4 text-brand-primary" />
                <span>Connect Cable...</span>
              </button>
              {onDuplicateNode && (
                <button
                  onClick={() => {
                    onDuplicateNode(contextMenu.node!);
                    setContextMenu((prev) => ({ ...prev, isOpen: false }));
                  }}
                  className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
                >
                  <Copy className="w-4 h-4 text-emerald-600" />
                  <span>Duplicate Device</span>
                </button>
              )}
              <button
                onClick={() => {
                  if (onSelectNode) onSelectNode(contextMenu.node!);
                  setContextMenu((prev) => ({ ...prev, isOpen: false }));
                }}
                className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
              >
                <Sliders className="w-4 h-4 text-brand-text-muted" />
                <span>Inspect Interfaces &amp; IP</span>
              </button>
              {onDeleteNode && (
                <button
                  onClick={() => {
                    onDeleteNode(contextMenu.node!.id);
                    setContextMenu((prev) => ({ ...prev, isOpen: false }));
                  }}
                  className="w-full px-3.5 py-2 text-left hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 flex items-center gap-2.5 border-t border-brand-border"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Delete Device</span>
                </button>
              )}
            </>
          )}

          {contextMenu.targetType === 'link' && contextMenu.link && (
            <>
              <div className="px-3.5 py-2 border-b border-brand-border font-mono text-[11px] font-bold text-brand-text-secondary">
                {contextMenu.link.src} ↔ {contextMenu.link.dst}
              </div>
              <button
                onClick={() => {
                  if (onSelectLink) onSelectLink(contextMenu.link!);
                  setContextMenu((prev) => ({ ...prev, isOpen: false }));
                }}
                className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
              >
                <Sliders className="w-4 h-4 text-brand-primary" />
                <span>Configure Speed &amp; Latency</span>
              </button>
              {onDeleteLink && (
                <button
                  onClick={() => {
                    onDeleteLink(contextMenu.link!.id);
                    setContextMenu((prev) => ({ ...prev, isOpen: false }));
                  }}
                  className="w-full px-3.5 py-2 text-left hover:bg-rose-50 dark:hover:bg-rose-950/40 text-rose-600 flex items-center gap-2.5 border-t border-brand-border"
                >
                  <Trash2 className="w-4 h-4" />
                  <span>Disconnect Cable</span>
                </button>
              )}
            </>
          )}

          {contextMenu.targetType === 'canvas' && (
            <>
              <button
                onClick={() => {
                  handleFitToScreen();
                  setContextMenu((prev) => ({ ...prev, isOpen: false }));
                }}
                className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
              >
                <Maximize2 className="w-4 h-4 text-brand-primary" />
                <span>Fit All Devices</span>
              </button>
              <button
                onClick={() => {
                  handleResetView();
                  setContextMenu((prev) => ({ ...prev, isOpen: false }));
                }}
                className="w-full px-3.5 py-2 text-left hover:bg-brand-bg flex items-center gap-2.5 text-brand-text-primary"
              >
                <RotateCcw className="w-4 h-4 text-brand-text-muted" />
                <span>Reset View (100%)</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};
