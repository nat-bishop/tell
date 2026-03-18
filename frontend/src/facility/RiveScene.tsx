"use client";

import { useState, useEffect, useRef } from "react";

interface RiveSceneProps {
  onRiveReady?: (rive: any) => void;
}

export function RiveScene({ onRiveReady }: RiveSceneProps) {
  const [riveModule, setRiveModule] = useState<any>(null);
  // Dynamic import of Rive module
  useEffect(() => {
    // Check if the .riv file is real (not a 0-byte placeholder)
    fetch("/facility.riv", { method: "HEAD" })
      .then((res) => {
        const len = parseInt(res.headers.get("content-length") ?? "0", 10);
        if (!res.ok || len < 100) return; // Placeholder or missing — skip Rive entirely
        return import("@rive-app/react-canvas");
      })
      .then((mod) => {
        if (mod) setRiveModule(mod);
      })
      .catch(() => {
        // Suppress — FacilityViewport CSS background is the fallback
      });
  }, []);

  if (!riveModule) {
    return null;
  }

  return (
    <RiveCanvas
      riveModule={riveModule}
      onRiveReady={onRiveReady}
    />
  );
}

function RiveCanvas({
  riveModule,
  onRiveReady,
}: {
  riveModule: any;
  onRiveReady?: (rive: any) => void;
}) {
  const { useRive, Fit, Alignment } = riveModule;
  const onRiveReadyRef = useRef(onRiveReady);
  onRiveReadyRef.current = onRiveReady;
  const [canvasReady, setCanvasReady] = useState(false);

  const { RiveComponent, rive } = useRive(
    {
      src: "/facility.riv",
      stateMachines: "facility_sm",
      layout: {
        fit: Fit.Cover,
        alignment: Alignment.Center,
      },
      autoplay: true,
      onLoadError: () => {
        // Suppress errors for missing .riv file
      },
      onLoad: () => {
        setCanvasReady(true);
      },
    },
    {
      fitCanvasToArtboardHeight: false,
      useDevicePixelRatio: true,
    }
  );

  useEffect(() => {
    if (rive && onRiveReadyRef.current) {
      onRiveReadyRef.current(rive);
    }
  }, [rive]);

  useEffect(() => {
    return () => {
      if (rive) {
        rive.cleanup?.();
      }
    };
  }, [rive]);

  if (!RiveComponent) {
    return null;
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        opacity: canvasReady ? 1 : 0,
        transition: "opacity 300ms ease-in",
      }}
    >
      <RiveComponent
        style={{
          width: "100%",
          height: "100%",
        }}
      />
    </div>
  );
}
