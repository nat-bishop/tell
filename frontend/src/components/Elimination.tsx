"use client";

import { useState, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";

export function Elimination() {
  const {
    eliminatedAlias,
    wasHuman,
    eliminationVoteCount,
    eliminationTieMessage,
    eliminationNoVotes,
  } = useGameStore();
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 0),
      setTimeout(() => setStep(2), 1500),
      setTimeout(() => setStep(3), 3000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  if (eliminationNoVotes) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-6">
        <p
          className="animate-fade-in font-[family-name:var(--font-literary)] text-[1.2rem]"
          style={{ color: "var(--ink)" }}
        >
          no consensus reached.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-6">
      {step >= 1 && (
        <p
          className="animate-fade-in font-[family-name:var(--font-literary)] text-[1.2rem]"
          style={{ color: "var(--ink)" }}
        >
          {eliminationTieMessage
            ? eliminationTieMessage
            : `${eliminatedAlias} received ${eliminationVoteCount} vote${eliminationVoteCount !== 1 ? "s" : ""}.`}
        </p>
      )}

      {step >= 2 && (
        <span className="animate-fade-in" style={{ color: "var(--dim)" }}>
          &middot;
        </span>
      )}

      {step >= 3 && (
        <p className="animate-elimination-reveal font-[family-name:var(--font-literary)] text-[1.2rem]">
          <span style={{ color: "var(--ink)" }}>{eliminatedAlias} was </span>
          <span style={{ color: wasHuman ? "var(--warm)" : "var(--ink)" }}>
            {wasHuman ? "human" : "ai"}
          </span>
          <span style={{ color: "var(--ink)" }}>.</span>
        </p>
      )}
    </div>
  );
}
