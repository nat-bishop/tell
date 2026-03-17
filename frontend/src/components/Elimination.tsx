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
    voteResults,
    players,
    comedyWinnerAlias,
    eliminatedId,
  } = useGameStore();
  const [step, setStep] = useState(0);

  // Timing (12s total):
  // 0ms   → step 1: vote map (who voted for whom)
  // 2500ms → step 2: line divider
  // 4000ms → step 3: beat (empty, let it breathe)
  // 5500ms → step 4: role reveal
  // 8500ms → step 5: verdict + comedy winner
  useEffect(() => {
    const timers = [
      setTimeout(() => setStep(1), 0),
      setTimeout(() => setStep(2), 2500),
      setTimeout(() => setStep(3), 4000),
      setTimeout(() => setStep(4), 5500),
      setTimeout(() => setStep(5), 8500),
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

  // Build vote map: voter aliases → target alias
  const aliasById: Record<string, string> = {};
  for (const p of players) {
    aliasById[p.id] = p.alias;
  }

  // voteResults is { targetId: [voterId, voterId, ...] }
  const voteMapEntries: { voterAliases: string[]; targetAlias: string; isEliminated: boolean }[] = [];
  if (voteResults) {
    for (const [targetId, voterIds] of Object.entries(voteResults)) {
      if (voterIds.length > 0) {
        voteMapEntries.push({
          voterAliases: voterIds.map((id) => aliasById[id] || "???"),
          targetAlias: aliasById[targetId] || "???",
          isEliminated: targetId === eliminatedId,
        });
      }
    }
    // Sort: eliminated target first, then by vote count descending
    voteMapEntries.sort((a, b) => {
      if (a.isEliminated && !b.isEliminated) return -1;
      if (!a.isEliminated && b.isEliminated) return 1;
      return b.voterAliases.length - a.voterAliases.length;
    });
  }

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8">
      {/* Step 1: Vote map — who voted for whom */}
      {step >= 1 && (
        <div className="animate-fade-in flex flex-col items-center gap-2">
          {eliminationTieMessage ? (
            <p className="font-system text-[1rem] text-ink tracking-wide">
              {eliminationTieMessage}
            </p>
          ) : (
            <>
              {voteMapEntries.length > 0 ? (
                <div className="flex flex-col items-center gap-1.5">
                  {voteMapEntries.map((entry) => (
                    <p
                      key={entry.targetAlias}
                      className="font-system text-[0.75rem] tracking-wide"
                    >
                      <span className="text-dim">
                        {entry.voterAliases.join(", ")}
                      </span>
                      <span className="text-dim mx-2">&rarr;</span>
                      <span className={entry.isEliminated ? "text-warm uppercase" : "text-ink uppercase"}>
                        {entry.targetAlias}
                      </span>
                    </p>
                  ))}
                </div>
              ) : (
                <p className="font-system text-[1rem] text-ink tracking-wide">
                  <span className="text-warm uppercase">{eliminatedAlias}</span>
                  {` received ${eliminationVoteCount} vote${eliminationVoteCount !== 1 ? "s" : ""}.`}
                </p>
              )}
            </>
          )}
        </div>
      )}

      {/* Step 2: Divider line */}
      {step >= 2 && (
        <div className="animate-line-draw h-px mx-auto" style={{ backgroundColor: 'var(--rule)' }} />
      )}

      {/* Step 3: Beat — empty space, let the moment breathe */}

      {/* Step 4: Role reveal */}
      {step >= 4 && (
        <p className="animate-reveal-hold font-system text-[1.1rem] tracking-[0.12em] uppercase">
          <span className="text-dim">{eliminatedAlias} was </span>
          <span
            className={`font-semibold ${wasHuman ? "text-warm glow-warm" : "text-cold glow-cold"}`}
          >
            {wasHuman ? "HUMAN" : "AI"}
          </span>
        </p>
      )}

      {/* Step 5: Verdict + comedy winner */}
      {step >= 5 && verdict && (
        <p className="animate-fade-in font-literary text-[1rem] italic text-dim max-w-md text-center leading-[1.6]">
          {verdict}
        </p>
      )}

      {step >= 5 && comedyWinnerAlias && (
        <p className="animate-fade-in font-system text-[0.7rem] text-dim tracking-wider uppercase mt-2">
          funniest: {comedyWinnerAlias}
        </p>
      )}
    </div>
  );
}
