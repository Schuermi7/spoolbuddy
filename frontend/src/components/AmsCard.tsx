import { AmsUnit, AmsTray } from "../lib/websocket";

interface AmsCardProps {
  unit: AmsUnit;
  printerModel?: string;
  numExtruders?: number;
}

// Get AMS display name from ID
function getAmsName(amsId: number): string {
  if (amsId <= 3) {
    return `AMS ${String.fromCharCode(65 + amsId)}`; // A, B, C, D
  } else if (amsId >= 128 && amsId <= 135) {
    return `AMS HT ${String.fromCharCode(65 + amsId - 128)}`; // HT-A, HT-B, ...
  } else if (amsId === 255) {
    return "External";
  } else if (amsId === 254) {
    return "External L";
  }
  return `AMS ${amsId}`;
}

// Check if AMS is HT type (single slot per unit)
function isHtAms(amsId: number): boolean {
  return amsId >= 128 && amsId <= 135;
}

// Convert hex color from printer (e.g., "FF0000FF") to CSS color
function trayColorToCSS(color: string | null): string {
  if (!color) return "#808080";
  const hex = color.slice(0, 6);
  return `#${hex}`;
}

// Check if a tray is empty
function isTrayEmpty(tray: AmsTray): boolean {
  return !tray.tray_type || tray.tray_type === "";
}

// Get humidity display info
function getHumidityDisplay(rawHumidity: number | null): { level: number; icon: string } {
  if (rawHumidity === null || rawHumidity === undefined || rawHumidity === 0) {
    return { level: 0, icon: "0" };
  }
  const level = Math.min(Math.max(rawHumidity, 1), 5);
  return { level, icon: String(Math.min(level, 4)) };
}

// Spool icon SVG - colored spool shape like OrcaSlicer
function SpoolIcon({ color, isEmpty, size = 32 }: { color: string; isEmpty: boolean; size?: number }) {
  if (isEmpty) {
    return (
      <div
        class="rounded-full border-2 border-dashed border-gray-500 flex items-center justify-center"
        style={{ width: size, height: size }}
      >
        <div class="w-2 h-2 rounded-full bg-gray-500" />
      </div>
    );
  }

  return (
    <svg width={size} height={size} viewBox="0 0 32 32">
      {/* Outer ring */}
      <circle cx="16" cy="16" r="14" fill={color} />
      {/* Inner shadow/depth */}
      <circle cx="16" cy="16" r="11" fill={color} style={{ filter: "brightness(0.85)" }} />
      {/* Highlight */}
      <ellipse cx="12" cy="12" rx="4" ry="3" fill="white" opacity="0.3" />
      {/* Center hole */}
      <circle cx="16" cy="16" r="5" fill="#2a2a2a" />
      <circle cx="16" cy="16" r="3" fill="#1a1a1a" />
    </svg>
  );
}

// Regular AMS card (4 slots)
function RegularAmsCard({ unit, printerModel }: AmsCardProps) {
  const amsName = getAmsName(unit.id);
  const humidity = getHumidityDisplay(unit.humidity);

  // Get nozzle label for multi-nozzle printers
  const nozzleLabel = unit.extruder !== undefined && unit.extruder !== null
    ? (unit.extruder === 0 ? "R" : "L")
    : null;
  const isMultiNozzle = printerModel && ["H2C", "H2D"].includes(printerModel.toUpperCase());

  // Build slots array (4 slots for regular AMS)
  const slots: (AmsTray | undefined)[] = [undefined, undefined, undefined, undefined];
  const sortedTrays = [...unit.trays].sort((a, b) => a.tray_id - b.tray_id);
  sortedTrays.forEach(tray => {
    if (tray.tray_id >= 0 && tray.tray_id < 4) {
      slots[tray.tray_id] = tray;
    }
  });

  return (
    <div class="relative bg-[#1e1e1e] rounded-lg overflow-hidden" style={{ width: 280 }}>
      {/* Header */}
      <div class="flex items-center justify-between px-3 py-2 bg-[#2a2a2a]">
        <div class="flex items-center gap-2">
          <span class="text-sm font-medium text-gray-200">{amsName}</span>
          {isMultiNozzle && nozzleLabel && (
            <span class={`px-1.5 py-0.5 text-xs rounded ${
              nozzleLabel === "L" ? "bg-blue-600 text-white" : "bg-purple-600 text-white"
            }`}>
              {nozzleLabel}
            </span>
          )}
        </div>
        <div class="flex items-center gap-1">
          <img
            src={`/images/ams/ams_humidity_${humidity.icon}.svg`}
            alt="Humidity"
            class="w-5 h-5 opacity-80"
          />
        </div>
      </div>

      {/* Spool icons row */}
      <div class="flex justify-around px-2 py-3 bg-[#252525]">
        {slots.map((tray, idx) => {
          const isEmpty = !tray || isTrayEmpty(tray);
          const color = tray ? trayColorToCSS(tray.tray_color) : "#808080";
          return (
            <div key={idx} class="flex flex-col items-center">
              <SpoolIcon color={color} isEmpty={isEmpty} size={36} />
            </div>
          );
        })}
      </div>

      {/* AMS unit image */}
      <div class="relative">
        <img
          src="/images/ams/ams.png"
          alt="AMS"
          class="w-full"
          style={{ filter: "brightness(0.9)" }}
        />
      </div>

      {/* Material labels */}
      <div class="flex justify-around px-2 py-2 bg-[#1a1a1a]">
        {slots.map((tray, idx) => {
          const isEmpty = !tray || isTrayEmpty(tray);
          const material = tray?.tray_type || "";
          const color = tray ? trayColorToCSS(tray.tray_color) : "#808080";
          return (
            <div key={idx} class="flex flex-col items-center" style={{ width: 56 }}>
              <span
                class="text-xs font-medium truncate text-center"
                style={{ color: isEmpty ? "#666" : color, maxWidth: 56 }}
                title={material}
              >
                {isEmpty ? "-" : material}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// HT AMS card (single slot)
function HtAmsCard({ unit, printerModel }: AmsCardProps) {
  const amsName = getAmsName(unit.id);
  const humidity = getHumidityDisplay(unit.humidity);
  const tray = unit.trays[0];
  const isEmpty = !tray || isTrayEmpty(tray);
  const color = tray ? trayColorToCSS(tray.tray_color) : "#808080";
  const material = tray?.tray_type || "";

  // Get nozzle label for multi-nozzle printers
  const nozzleLabel = unit.extruder !== undefined && unit.extruder !== null
    ? (unit.extruder === 0 ? "R" : "L")
    : null;
  const isMultiNozzle = printerModel && ["H2C", "H2D"].includes(printerModel.toUpperCase());

  return (
    <div class="relative bg-[#1e1e1e] rounded-lg overflow-hidden" style={{ width: 140 }}>
      {/* Header */}
      <div class="flex items-center justify-between px-3 py-2 bg-[#2a2a2a]">
        <div class="flex items-center gap-1">
          <span class="text-xs font-medium text-gray-200">{amsName}</span>
          {isMultiNozzle && nozzleLabel && (
            <span class={`px-1 py-0.5 text-xs rounded ${
              nozzleLabel === "L" ? "bg-blue-600 text-white" : "bg-purple-600 text-white"
            }`}>
              {nozzleLabel}
            </span>
          )}
        </div>
        <img
          src={`/images/ams/ams_humidity_${humidity.icon}.svg`}
          alt="Humidity"
          class="w-4 h-4 opacity-80"
        />
      </div>

      {/* Spool icon */}
      <div class="flex justify-center py-2 bg-[#252525]">
        <SpoolIcon color={color} isEmpty={isEmpty} size={40} />
      </div>

      {/* AMS HT image */}
      <div class="relative flex justify-center">
        <img
          src="/images/ams/amsht.png"
          alt="AMS HT"
          class="h-32 object-contain"
          style={{ filter: "brightness(0.9)" }}
        />
      </div>

      {/* Material label */}
      <div class="flex justify-center px-2 py-2 bg-[#1a1a1a]">
        <span
          class="text-xs font-medium truncate"
          style={{ color: isEmpty ? "#666" : color }}
          title={material}
        >
          {isEmpty ? "-" : material}
        </span>
      </div>
    </div>
  );
}

export function AmsCard({ unit, printerModel, numExtruders = 1 }: AmsCardProps) {
  const isHt = isHtAms(unit.id);

  if (isHt) {
    return <HtAmsCard unit={unit} printerModel={printerModel} numExtruders={numExtruders} />;
  }

  return <RegularAmsCard unit={unit} printerModel={printerModel} numExtruders={numExtruders} />;
}

// External spool holder (Virtual Tray)
interface ExternalSpoolProps {
  tray: AmsTray | null;
  position?: "left" | "right";
  numExtruders?: number;
}

export function ExternalSpool({ tray, position, numExtruders = 1 }: ExternalSpoolProps) {
  if (!tray || isTrayEmpty(tray)) {
    return null;
  }

  const color = trayColorToCSS(tray.tray_color);
  const label = numExtruders === 1
    ? "External"
    : (position === "left" ? "External L" : "External R");

  return (
    <div class="bg-[#1e1e1e] rounded-lg overflow-hidden" style={{ width: 100 }}>
      <div class="px-2 py-1.5 bg-[#2a2a2a]">
        <span class="text-xs font-medium text-gray-200">{label}</span>
      </div>
      <div class="flex flex-col items-center py-3 gap-2">
        <SpoolIcon color={color} isEmpty={false} size={44} />
        <span class="text-xs font-medium" style={{ color }}>
          {tray.tray_type}
        </span>
      </div>
    </div>
  );
}
