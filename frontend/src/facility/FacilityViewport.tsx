"use client";

interface FacilityViewportProps {
  children: React.ReactNode;
}

export function FacilityViewport({ children }: FacilityViewportProps) {
  return (
    <div className="facility-viewport">
      <div className="facility-vignette" />
      <div style={{ position: "relative", zIndex: 10, width: "100%", height: "100%" }}>
        {children}
      </div>
    </div>
  );
}
