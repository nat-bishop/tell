"use client";

import { ZONES, type ZoneName } from "@/facility/zones";

interface PanelProps {
  zone: ZoneName;
  children: React.ReactNode;
  className?: string;
  entering?: boolean;
  exiting?: boolean;
}

export function Panel({ zone, children, className, entering, exiting }: PanelProps) {
  const z = ZONES[zone];
  if (!z) return null;

  const animClass = exiting
    ? "animate-panel-exit"
    : entering
      ? "animate-panel-enter"
      : "";

  return (
    <div
      className={`facility-panel ${animClass} ${className ?? ""}`}
      style={{
        position: "absolute",
        top: z.top,
        bottom: z.bottom,
        left: z.left,
        right: z.right,
        width: z.width,
        height: z.height,
      }}
    >
      <div style={{ padding: 20, overflowY: "auto", position: "relative", zIndex: 1, height: "100%" }}>
        {children}
      </div>
    </div>
  );
}
