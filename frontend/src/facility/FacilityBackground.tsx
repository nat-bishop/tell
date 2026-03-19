"use client";

import { useMemo } from "react";
import { usePhaseLayout } from "./usePhaseLayout";

// Room-index → radial gradient position/spread
const GRADIENT_CONFIGS: Record<number, string[]> = {
  0: ["ellipse at 50% 30%"],
  1: ["ellipse at 50% 20%"],
  2: ["ellipse at 50% 50%"],
  3: ["ellipse at 30% 50%", "ellipse at 70% 50%"],
  4: ["ellipse at 50% 40%"],
};

// Deterministic particle positions — no randomness per render
const PARTICLES = [
  { left: 8, delay: 0, duration: 18 },
  { left: 16, delay: 3, duration: 22 },
  { left: 24, delay: 7, duration: 19 },
  { left: 33, delay: 11, duration: 24 },
  { left: 41, delay: 2, duration: 20 },
  { left: 50, delay: 9, duration: 17 },
  { left: 58, delay: 5, duration: 23 },
  { left: 67, delay: 14, duration: 21 },
  { left: 75, delay: 1, duration: 18 },
  { left: 83, delay: 8, duration: 25 },
  { left: 91, delay: 12, duration: 20 },
  { left: 12, delay: 16, duration: 22 },
];

function buildBackground(
  roomIndex: number,
  accentColor: number,
  brightness: number,
): string {
  const r = Math.round(91 + (224 - 91) * accentColor);
  const g = Math.round(143 + (122 - 143) * accentColor);
  const b = Math.round(185 + (95 - 185) * accentColor);
  const alpha = 0.08 + brightness * 0.14;
  const color = `rgba(${r},${g},${b},${alpha})`;

  const shapes = GRADIENT_CONFIGS[roomIndex] ?? GRADIENT_CONFIGS[0];
  const gradients = shapes.map(
    (shape) => `radial-gradient(${shape}, ${color} 0%, transparent 70%)`,
  );
  return gradients.join(", ");
}

export function FacilityBackground() {
  const layout = usePhaseLayout();

  const background = useMemo(
    () => buildBackground(layout.roomIndex, layout.accentColor, layout.brightness),
    [layout],
  );

  return (
    <>
      <div
        className="facility-bg"
        style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none", background }}
      />
      <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
        {PARTICLES.map((p, i) => (
          <div
            key={i}
            className="facility-particle"
            style={{
              left: `${p.left}%`,
              bottom: 0,
              animationDuration: `${p.duration}s`,
              animationDelay: `${p.delay}s`,
            }}
          />
        ))}
      </div>
    </>
  );
}
