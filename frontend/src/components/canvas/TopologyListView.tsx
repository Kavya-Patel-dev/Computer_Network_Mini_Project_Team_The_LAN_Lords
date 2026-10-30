import React from 'react';
import { Topology, NetworkNode, NetworkLink } from '../../types/network';
import { CiscoDeviceGlyph } from './CiscoDeviceGlyph';
import { getHardwareDefinition } from '../../mock/ciscoHardware';
import { ArrowRight, Trash2 } from 'lucide-react';

interface TopologyListViewProps {
  topology: Topology;
  onDeleteNode?: (nodeId: string) => void;
  onDeleteLink?: (linkId: string) => void;
  editable?: boolean;
}

export const TopologyListView: React.FC<TopologyListViewProps> = ({
  topology,
  onDeleteNode,
  onDeleteLink,
  editable = false,
}) => {
  return (
    <div className="space-y-6">
      {/* Nodes Section */}
      <div className="bg-brand-surface border border-brand-border rounded-lg p-4">
        <h3 className="text-h3 font-semibold text-brand-text-primary mb-3 flex items-center justify-between">
          <span>Configured Nodes ({topology.nodes.length})</span>
          <span className="text-caption text-brand-text-muted">Accessible Node Roster</span>
        </h3>
        <div className="divide-y divide-brand-border">
          {topology.nodes.map((node) => {
            const hw = getHardwareDefinition(node.type, node.category);
            return (
              <div key={node.id} className="py-2.5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-brand-bg border border-brand-border flex items-center justify-center p-1">
                    <CiscoDeviceGlyph shape={hw.iconShape} size={28} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-body font-bold text-brand-text-primary">{node.id}</span>
                      <span className="text-[10px] uppercase font-mono tracking-wider px-1.5 py-0.5 rounded bg-brand-bg border border-brand-border text-brand-text-muted">
                        {hw.shortName}
                      </span>
                    </div>
                    <p className="text-caption text-brand-text-secondary">{node.label}</p>
                  </div>
                </div>
                {editable && onDeleteNode && (
                  <button
                    onClick={() => onDeleteNode(node.id)}
                    className="p-1.5 text-brand-text-muted hover:text-rose-600 rounded focus:outline-none"
                    aria-label={`Delete ${node.id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Links Section */}
      <div className="bg-brand-surface border border-brand-border rounded-lg p-4">
        <h3 className="text-h3 font-semibold text-brand-text-primary mb-3 flex items-center justify-between">
          <span>Configured Interconnects ({topology.links.length})</span>
          <span className="text-caption text-brand-text-muted">Physical Links & Capacities</span>
        </h3>
        <div className="divide-y divide-brand-border">
          {topology.links.map((link) => (
            <div key={link.id} className="py-2.5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="font-mono text-body font-semibold text-brand-text-primary flex items-center gap-1.5">
                  <span>{link.src}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-brand-text-muted" />
                  <span>{link.dst}</span>
                </div>
                <div className="flex items-center gap-2 text-caption text-brand-text-secondary">
                  <span className="px-2 py-0.5 bg-brand-bg border border-brand-border rounded font-mono">
                    {link.bandwidth_mbps} Mbps
                  </span>
                  {link.simulationIncluded === false && <span className="text-[10px] text-amber-700">management only; excluded from simulation</span>}
                  <span>•</span>
                  <span>{link.latency_ms} ms</span>
                  {link.loss_percent > 0 && (
                    <>
                      <span>•</span>
                      <span className="text-rose-600 font-medium">{link.loss_percent}% Loss</span>
                    </>
                  )}
                </div>
              </div>
              {editable && onDeleteLink && (
                <button
                  onClick={() => onDeleteLink(link.id)}
                  className="p-1.5 text-brand-text-muted hover:text-rose-600 rounded focus:outline-none"
                  aria-label={`Delete link ${link.id}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
