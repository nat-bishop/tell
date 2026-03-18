"use client";

import { useState, useRef, useCallback, useEffect } from "react";

export type TransitionState = "idle" | "lockdown" | "reconfigure" | "boot" | "snap";

export function useTransitionMachine() {
  const [state, setState] = useState<TransitionState>("idle");
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = useCallback(() => {
    for (const t of timersRef.current) clearTimeout(t);
    timersRef.current = [];
  }, []);

  const startTransition = useCallback(
    (holdMs: number) => {
      clearTimers();
      setState("lockdown");

      const lockdownDur = 300;
      const bootDur = 400;
      const reconfigureDur = Math.max(0, holdMs - lockdownDur - bootDur);

      const t1 = setTimeout(() => setState("reconfigure"), lockdownDur);
      const t2 = setTimeout(() => setState("boot"), lockdownDur + reconfigureDur);
      const t3 = setTimeout(() => setState("idle"), lockdownDur + reconfigureDur + bootDur);

      timersRef.current = [t1, t2, t3];
    },
    [clearTimers],
  );

  const snapTo = useCallback(() => {
    clearTimers();
    setState("idle");
  }, [clearTimers]);

  useEffect(() => {
    return () => clearTimers();
  }, [clearTimers]);

  return { transitionState: state, startTransition, snapTo } as const;
}
