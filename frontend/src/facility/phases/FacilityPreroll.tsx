"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { Panel } from "@/facility/Panel";

const ROUND_INFO: Record<string, { name: string; directive: string }> = {
  task: {
    name: "GALLERY VOTE",
    directive: "answer a prompt. vote for the most human. votes cost points.",
  },
  brain_test: {
    name: "QUICK DRAW",
    directive: "5 rapid-fire questions. pick the right answer before time runs out.",
  },
  wager: {
    name: "NUMBER LINE",
    directive: "estimate a number. then bet on who got closest.",
  },
  signal: {
    name: "SIGNAL",
    directive: "transmitters encode a phrase. everyone else decodes it.",
  },
};

export function FacilityPreroll() {
  const roundType = useGameStore((s) => s.roundType);
  const roundNumber = useGameStore((s) => s.roundNumber);
  const totalRounds = useGameStore((s) => s.totalRounds);

  const info = ROUND_INFO[roundType ?? ""] ?? ROUND_INFO.task;

  return (
    <Panel zone="wall-display">
      <div className="animate-interstitial-in interstitial-scan flex h-full flex-col items-center justify-center gap-4">
        <p
          className="animate-fade-in font-system text-[0.65rem] text-dim tracking-[0.2em] uppercase"
          style={{ animationDelay: "0.3s" }}
        >
          round {roundNumber} of {totalRounds}
        </p>

        <p
          className="font-system text-[1.4rem] text-ink tracking-[0.2em] uppercase"
          style={{ textShadow: "0 0 30px var(--cold-glow)" }}
        >
          {info.name}
        </p>

        <hr
          className="animate-line-draw border-none"
          style={{
            animationDelay: "1s",
            height: "1px",
            background: "var(--rule)",
          }}
        />

        <p
          className="animate-fade-in font-literary text-[0.95rem] text-dim tracking-[0.05em] lowercase"
          style={{
            animationDelay: "1.5s",
            maxWidth: "24rem",
            textAlign: "center",
            lineHeight: "1.5",
          }}
        >
          {info.directive}
        </p>
      </div>
    </Panel>
  );
}
