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
    verdict,
  } = useGameStore();
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 0),
      setTimeout(() => setStep(2), 2000),
      setTimeout(() => setStep(3), 3500),
      setTimeout(() => setStep(4), 5500),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  if (eliminationNoVotes) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8">
        <p className="animate-fade-in font-literary text-[1.2rem] text-ink">
          no consensus reached.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8">
      {step >= 1 && (
        <p className="animate-fade-in font-literary text-[1.2rem] text-ink">
          {eliminationTieMessage
            ? eliminationTieMessage
            : `${eliminatedAlias} received ${eliminationVoteCount} vote${eliminationVoteCount !== 1 ? "s" : ""}.`}
        </p>
      )}

      {step >= 2 && (
        <div className="animate-line-draw h-px bg-rule mx-auto" />
      )}

      {step >= 3 && (
        <p className="animate-reveal-expand font-literary text-[1.2rem]">
          <span className="text-ink">{eliminatedAlias} was </span>
          <span
            className={`font-semibold ${wasHuman ? "text-warm" : "text-ink"}`}
          >
            {wasHuman ? "human" : "ai"}
          </span>
          <span className="text-ink">.</span>
        </p>
      )}

      {step >= 4 && verdict && (
        <p className="animate-fade-in font-literary text-[1rem] italic text-dim max-w-md text-center leading-[1.6]">
          {verdict}
        </p>
      )}
    </div>
  );
}
