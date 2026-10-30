import React from 'react';

export type GlyphShape =
  | 'router'
  | 'switch'
  | 'l3switch'
  | 'hub'
  | 'wireless'
  | 'firewall'
  | 'cloud'
  | 'pc'
  | 'laptop'
  | 'server'
  | 'phone'
  | 'printer'
  | 'tablet'
  | 'smartphone'
  | 'iot';

interface CiscoDeviceGlyphProps {
  shape: GlyphShape;
  size?: number;
  isSelected?: boolean;
  isFailed?: boolean;
  className?: string;
}

export const CiscoDeviceGlyph: React.FC<CiscoDeviceGlyphProps> = ({
  shape,
  size = 44,
  isSelected = false,
  isFailed = false,
  className = '',
}) => {
  const baseFill = isFailed ? '#EF4444' : isSelected ? '#2563EB' : undefined;

  const renderShape = () => {
    switch (shape) {
      // Authentic Cisco Circular Router with 4 Arrows
      case 'router':
        return (
          <g>
            <circle cx="24" cy="24" r="21" fill={baseFill || '#0284C7'} stroke={isSelected ? '#1D4ED8' : '#0369A1'} strokeWidth="2" />
            <circle cx="24" cy="24" r="18" fill="none" stroke="#FFFFFF" strokeOpacity="0.3" strokeWidth="1" />
            {/* 4 Inward/Outward Cisco Router Arrows */}
            <path d="M14 24 H34" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M24 14 V34" stroke="#FFFFFF" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M17 21 L14 24 L17 27" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M31 21 L34 24 L31 27" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M21 17 L24 14 L27 17" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M21 31 L24 34 L27 31" fill="none" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </g>
        );

      // Cisco Layer 2 Switch (Rectangular with 2-way opposite arrows)
      case 'switch':
        return (
          <g>
            <rect x="5" y="11" width="38" height="26" rx="4" fill={baseFill || '#0369A1'} stroke={isSelected ? '#1D4ED8' : '#075985'} strokeWidth="2" />
            {/* Top row arrow pointing right */}
            <line x1="12" y1="18" x2="33" y2="18" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
            <path d="M29 15 L34 18 L29 21" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            {/* Bottom row arrow pointing left */}
            <line x1="36" y1="29" x2="15" y2="29" stroke="#FFFFFF" strokeWidth="2.2" strokeLinecap="round" />
            <path d="M19 26 L14 29 L19 32" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            {/* Port LED markers */}
            <circle cx="8" cy="18" r="1.5" fill="#34D399" />
            <circle cx="8" cy="29" r="1.5" fill="#34D399" />
          </g>
        );

      // Cisco Layer 3 Multilayer Switch (3560/3650 cross arrows)
      case 'l3switch':
        return (
          <g>
            <rect x="5" y="9" width="38" height="30" rx="5" fill={baseFill || '#1E3A8A'} stroke={isSelected ? '#3B82F6' : '#172554'} strokeWidth="2" />
            {/* L3 Cross Arrows (Switching + Routing) */}
            <circle cx="24" cy="24" r="11" fill="#1D4ED8" stroke="#60A5FA" strokeWidth="1" />
            <path d="M17 24 H31" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
            <path d="M24 17 V31" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
            <path d="M19 22 L17 24 L19 26" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M29 22 L31 24 L29 26" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M22 19 L24 17 L26 19" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M22 29 L24 31 L26 29" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            {/* Port LEDs */}
            <circle cx="8" cy="14" r="1.2" fill="#4ADE80" />
            <circle cx="8" cy="19" r="1.2" fill="#4ADE80" />
            <circle cx="8" cy="24" r="1.2" fill="#4ADE80" />
          </g>
        );

      // Hub / Multiport Repeater
      case 'hub':
        return (
          <g>
            <rect x="6" y="13" width="36" height="22" rx="3" fill={baseFill || '#475569'} stroke="#334155" strokeWidth="2" />
            {/* Hub Collision Domain Broadcast Lines */}
            <line x1="12" y1="24" x2="36" y2="24" stroke="#FFFFFF" strokeWidth="2" strokeLinecap="round" />
            <circle cx="16" cy="24" r="2.5" fill="#F8FAFC" />
            <circle cx="24" cy="24" r="2.5" fill="#F8FAFC" />
            <circle cx="32" cy="24" r="2.5" fill="#F8FAFC" />
            <line x1="16" y1="18" x2="16" y2="30" stroke="#FFFFFF" strokeWidth="1.5" />
            <line x1="24" y1="18" x2="24" y2="30" stroke="#FFFFFF" strokeWidth="1.5" />
            <line x1="32" y1="18" x2="32" y2="30" stroke="#FFFFFF" strokeWidth="1.5" />
          </g>
        );

      // Cisco Wireless Router (WRT300N / AP)
      case 'wireless':
        return (
          <g>
            {/* Dual Dipole Antennas */}
            <line x1="14" y1="16" x2="9" y2="6" stroke="#0284C7" strokeWidth="2.5" strokeLinecap="round" />
            <line x1="34" y1="16" x2="39" y2="6" stroke="#0284C7" strokeWidth="2.5" strokeLinecap="round" />
            {/* Radio Wave Arcs */}
            <path d="M21 9 A5 5 0 0 1 27 9" fill="none" stroke="#38BDF8" strokeWidth="1.8" strokeLinecap="round" />
            <path d="M18 6 A9 9 0 0 1 30 6" fill="none" stroke="#38BDF8" strokeWidth="1.8" strokeLinecap="round" />
            {/* Base Box */}
            <rect x="7" y="16" width="34" height="22" rx="4" fill={baseFill || '#0891B2'} stroke="#0E7490" strokeWidth="2" />
            {/* Front Bezel LEDs */}
            <circle cx="12" cy="27" r="1.8" fill="#4ADE80" />
            <circle cx="17" cy="27" r="1.8" fill="#38BDF8" />
            <circle cx="22" cy="27" r="1.8" fill="#38BDF8" />
            <circle cx="27" cy="27" r="1.8" fill="#38BDF8" />
            <circle cx="32" cy="27" r="1.8" fill="#FACC15" />
          </g>
        );

      // Cisco ASA 5506-X Security Appliance / Firewall
      case 'firewall':
        return (
          <g>
            <rect x="6" y="10" width="36" height="28" rx="4" fill={baseFill || '#B45309'} stroke="#78350F" strokeWidth="2" />
            {/* Brick Wall Pattern */}
            <line x1="6" y1="19" x2="42" y2="19" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="6" y1="28" x2="42" y2="28" stroke="#FEF3C7" strokeWidth="1.5" />
            {/* Brick Vertical Joints */}
            <line x1="18" y1="10" x2="18" y2="19" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="30" y1="10" x2="30" y2="19" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="12" y1="19" x2="12" y2="28" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="24" y1="19" x2="24" y2="28" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="36" y1="19" x2="36" y2="28" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="18" y1="28" x2="18" y2="38" stroke="#FEF3C7" strokeWidth="1.5" />
            <line x1="30" y1="28" x2="30" y2="38" stroke="#FEF3C7" strokeWidth="1.5" />
            {/* Central Security Shield */}
            <path d="M24 16 L29 19 V24 C29 27 24 30 24 30 C24 30 19 27 19 24 V19 Z" fill="#DC2626" stroke="#FEF08A" strokeWidth="1" />
          </g>
        );

      // Cloud-PT / WAN Emulation Cloud
      case 'cloud':
        return (
          <g>
            <path
              d="M17 34 C12 34 8 30 8 25 C8 21 11 18 15 17.5 C16 12 21 8 27 8 C33 8 38 12.5 39 18 C43 19 46 22 46 26 C46 30.5 42.5 34 38 34 Z"
              fill={baseFill || '#0284C7'}
              stroke="#0369A1"
              strokeWidth="2"
            />
            {/* Internal WAN Lightning / Data Pulse */}
            <path d="M25 15 L20 23 H26 L23 31 L30 21 H24 Z" fill="#FDE047" stroke="#CA8A04" strokeWidth="0.8" />
          </g>
        );

      // PC Desktop
      case 'pc':
        return (
          <g>
            {/* Monitor */}
            <rect x="8" y="8" width="32" height="22" rx="3" fill="#1E293B" stroke={baseFill || '#059669'} strokeWidth="2" />
            <rect x="11" y="11" width="26" height="16" rx="1.5" fill="#10B981" fillOpacity="0.25" />
            {/* Code lines on screen */}
            <line x1="14" y1="15" x2="28" y2="15" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="14" y1="19" x2="24" y2="19" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="14" y1="23" x2="20" y2="23" stroke="#34D399" strokeWidth="1.5" strokeLinecap="round" />
            {/* Stand */}
            <path d="M21 30 V35 H15 V38 H33 V35 H27 V30" fill="#334155" stroke="#1E293B" strokeWidth="1.5" />
          </g>
        );

      // Laptop
      case 'laptop':
        return (
          <g>
            {/* Open Display */}
            <rect x="10" y="10" width="28" height="20" rx="2" fill="#1E293B" stroke={baseFill || '#0D9488'} strokeWidth="1.8" />
            <rect x="13" y="13" width="22" height="14" rx="1" fill="#0D9488" fillOpacity="0.2" />
            <line x1="16" y1="17" x2="26" y2="17" stroke="#2DD4BF" strokeWidth="1.2" strokeLinecap="round" />
            <line x1="16" y1="21" x2="30" y2="21" stroke="#2DD4BF" strokeWidth="1.2" strokeLinecap="round" />
            {/* Base Keyboard */}
            <path d="M5 33 L9 30 H39 L43 33 H5 Z" fill="#475569" stroke="#1E293B" strokeWidth="1.5" />
            <rect x="20" y="31.5" width="8" height="1.5" rx="0.5" fill="#94A3B8" />
          </g>
        );

      // Server (Rack Tower with Drive Bays)
      case 'server':
        return (
          <g>
            <rect x="11" y="7" width="26" height="34" rx="4" fill="#1E1B4B" stroke={baseFill || '#7C3AED'} strokeWidth="2" />
            {/* Bay 1 */}
            <rect x="14" y="11" width="20" height="7" rx="1.5" fill="#312E81" />
            <circle cx="30" cy="14.5" r="1.3" fill="#A78BFA" />
            <circle cx="26" cy="14.5" r="1.3" fill="#34D399" />
            <line x1="17" y1="14.5" x2="22" y2="14.5" stroke="#6366F1" strokeWidth="1" />
            {/* Bay 2 */}
            <rect x="14" y="20" width="20" height="7" rx="1.5" fill="#312E81" />
            <circle cx="30" cy="23.5" r="1.3" fill="#A78BFA" />
            <circle cx="26" cy="23.5" r="1.3" fill="#34D399" />
            <line x1="17" y1="23.5" x2="22" y2="23.5" stroke="#6366F1" strokeWidth="1" />
            {/* Bay 3 */}
            <rect x="14" y="29" width="20" height="7" rx="1.5" fill="#312E81" />
            <circle cx="30" cy="32.5" r="1.3" fill="#A78BFA" />
            <circle cx="26" cy="32.5" r="1.3" fill="#34D399" />
            <line x1="17" y1="32.5" x2="22" y2="32.5" stroke="#6366F1" strokeWidth="1" />
          </g>
        );

      // Cisco IP Phone 7960
      case 'phone':
        return (
          <g>
            <rect x="9" y="8" width="30" height="32" rx="4" fill="#334155" stroke={baseFill || '#2563EB'} strokeWidth="2" />
            {/* LCD Screen */}
            <rect x="13" y="11" width="16" height="11" rx="1" fill="#93C5FD" fillOpacity="0.3" stroke="#60A5FA" strokeWidth="1" />
            <line x1="15" y1="14" x2="25" y2="14" stroke="#93C5FD" strokeWidth="1" />
            {/* Handset */}
            <path d="M32 9 C35 9 37 11 37 14 V34 C37 37 35 39 32 39 Z" fill="#1E293B" stroke="#0F172A" strokeWidth="1.2" />
            {/* Keypad */}
            <circle cx="16" cy="26" r="1.2" fill="#F8FAFC" />
            <circle cx="21" cy="26" r="1.2" fill="#F8FAFC" />
            <circle cx="26" cy="26" r="1.2" fill="#F8FAFC" />
            <circle cx="16" cy="31" r="1.2" fill="#F8FAFC" />
            <circle cx="21" cy="31" r="1.2" fill="#F8FAFC" />
            <circle cx="26" cy="31" r="1.2" fill="#F8FAFC" />
            <circle cx="21" cy="35" r="1.2" fill="#F8FAFC" />
          </g>
        );

      // Network Laser Printer
      case 'printer':
        return (
          <g>
            {/* Printer Paper Tray Input */}
            <rect x="15" y="7" width="18" height="8" rx="1" fill="#E2E8F0" stroke="#94A3B8" strokeWidth="1" />
            {/* Printer Body */}
            <rect x="8" y="15" width="32" height="18" rx="3" fill="#475569" stroke={baseFill || '#0284C7'} strokeWidth="2" />
            {/* Output Slot & Page */}
            <rect x="14" y="24" width="20" height="12" rx="1" fill="#F8FAFC" stroke="#CBD5E1" strokeWidth="1" />
            <line x1="17" y1="28" x2="30" y2="28" stroke="#94A3B8" strokeWidth="1" />
            <line x1="17" y1="31" x2="26" y2="31" stroke="#94A3B8" strokeWidth="1" />
            {/* Status LED */}
            <circle cx="34" cy="19" r="1.5" fill="#34D399" />
          </g>
        );

      // Tablet PC
      case 'tablet':
        return (
          <g>
            <rect x="11" y="6" width="26" height="36" rx="4" fill="#0F172A" stroke={baseFill || '#3B82F6'} strokeWidth="2" />
            <rect x="13.5" y="10" width="21" height="28" rx="2" fill="#1E293B" />
            <circle cx="24" cy="8" r="0.8" fill="#64748B" />
            <circle cx="24" cy="40" r="1.2" fill="#64748B" />
          </g>
        );

      // Smartphone
      case 'smartphone':
        return (
          <g>
            <rect x="14" y="7" width="20" height="34" rx="4" fill="#0F172A" stroke={baseFill || '#8B5CF6'} strokeWidth="2" />
            <rect x="16" y="11" width="16" height="26" rx="2" fill="#1E293B" />
            <circle cx="24" cy="9" r="0.8" fill="#64748B" />
            <line x1="21" y1="39" x2="27" y2="39" stroke="#64748B" strokeWidth="1.2" strokeLinecap="round" />
          </g>
        );

      // Generic IoT Device / Microcontroller
      case 'iot':
        return (
          <g>
            <rect x="12" y="12" width="24" height="24" rx="3" fill="#065F46" stroke={baseFill || '#10B981'} strokeWidth="2" />
            {/* Chip pins */}
            <line x1="16" y1="8" x2="16" y2="12" stroke="#F59E0B" strokeWidth="1.5" />
            <line x1="24" y1="8" x2="24" y2="12" stroke="#F59E0B" strokeWidth="1.5" />
            <line x1="32" y1="8" x2="32" y2="12" stroke="#F59E0B" strokeWidth="1.5" />
            <line x1="16" y1="36" x2="16" y2="40" stroke="#F59E0B" strokeWidth="1.5" />
            <line x1="24" y1="36" x2="24" y2="40" stroke="#F59E0B" strokeWidth="1.5" />
            <line x1="32" y1="36" x2="32" y2="40" stroke="#F59E0B" strokeWidth="1.5" />
            <circle cx="24" cy="24" r="5" fill="#047857" stroke="#34D399" strokeWidth="1.2" />
            <circle cx="24" cy="24" r="2" fill="#FDE047" />
          </g>
        );

      default:
        return (
          <circle cx="24" cy="24" r="18" fill="#2563EB" stroke="#1D4ED8" strokeWidth="2" />
        );
    }
  };

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`shrink-0 transition-transform ${className}`}
    >
      {renderShape()}
    </svg>
  );
};
