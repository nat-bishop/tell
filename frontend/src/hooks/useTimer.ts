"use client";

import { useState, useEffect } from "react";

export function useTimer(deadline: string | null): number {
  const [remaining, setRemaining] = useState(0);

  useEffect(() => {
    if (!deadline) {
      setRemaining(0);
      return;
    }

    const update = () => {
      const diff = new Date(deadline).getTime() - Date.now();
      setRemaining(Math.max(0, Math.floor(diff / 1000)));
    };

    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [deadline]);

  return remaining;
}
