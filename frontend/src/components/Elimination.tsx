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
        <p className="animate-fade-in font-system text-[1rem] text-dim tracking-wider uppercase">
          no consensus reached.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8">
      {step >= 1 && (
        <p className="animate-fade-in font-system text-[1rem] text-ink tracking-wide">
          {eliminationTieMessage
            ? eliminationTieMessage
            : (
              <>
                <span className="text-warm uppercase">{eliminatedAlias}</span>
                {` received ${eliminationVoteCount} vote${eliminationVoteCount !== 1 ? "s" : ""}.`}
              </>
            )}
        </p>
      )}

      {step >= 2 && (
        <div className="animate-line-draw h-px mx-auto" style={{ backgroundColor: 'var(--rule)' }} />
      )}

      {step >= 3 && (
        <p className="animate-reveal-expand font-system text-[1.1rem] tracking-[0.12em] uppercase">
          <span className="text-dim">{eliminatedAlias} was </span>
          <span
            className={`font-semibold ${wasHuman ? "text-warm glow-warm" : "text-cold glow-cold"}`}
          >
            {wasHuman ? "HUMAN" : "AI"}
          </span>
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
