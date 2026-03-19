"use client";

import { ZONES, type ZoneName } from "@/facility/zones";

interface PanelProps {
  zone: ZoneName;
  children: React.ReactNode;
  className?: string;
}

export function Panel({ zone, children, className }: PanelProps) {
  const z = ZONES[zone];
  if (!z) return null;

  return (
    <div
      className={`facility-panel ${className ?? ""}`}
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
