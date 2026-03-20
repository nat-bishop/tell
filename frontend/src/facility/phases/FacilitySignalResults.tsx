"use client";

import { useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

function JudgmentIcon({ score }: { score: number }) {
  if (score >= 2) {
    return <span className="font-system text-[0.6rem] shrink-0 tracking-wide uppercase text-cold">{"\u2713"}</span>;
  }
  if (score === 1) {
    return <span className="font-system text-[0.6rem] shrink-0 tracking-wide uppercase text-dim">{"~"}</span>;
  }
  return <span className="font-system text-[0.6rem] shrink-0 tracking-wide uppercase text-warm">{"\u2717"}</span>;
}

export function FacilitySignalResults() {
  const roundResults = useGameStore((s) => s.roundResults);
  const roundScores = useGameStore((s) => s.roundScores);
  const scores = useGameStore((s) => s.scores);

  const isSignal = roundResults?.round_type === "signal";

  const entries = useMemo(() => {
    if (!roundResults || roundResults.round_type !== "signal") return [];
    return Object.entries(roundResults.results);
  }, [roundResults]);

  if (!isSignal) {
    return (
      <Panel zone="full-screen">
        <div className="flex items-center justify-center h-full">
          <SystemText>loading results...</SystemText>
        </div>
      </Panel>
    );
  }

  return (
    <Panel zone="full-screen">
      <div className="flex flex-col gap-6 pt-4">
        <div className="text-center">
          <p className="font-system text-[0.85rem] text-dim tracking-wider uppercase">
            signal results
          </p>
          <p className="font-system text-[0.55rem] text-cold tracking-[0.15em] uppercase mt-1">
            {roundResults.constraint}
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {entries.map(([pid, data], idx) => {
            const delta = roundScores?.[pid] ?? 0;
            const total = scores[pid] ?? 0;
            const guessEntries = Object.entries(data.guesses);

            return (
              <div
                key={pid}
                className="card p-4 animate-fade-in"
                style={{ animationDelay: `${idx * 150}ms` }}
              >
                {/* Header: alias + score */}
                <div className="flex items-baseline justify-between mb-3">
                  <p className="font-literary-sc text-[0.8rem] text-dim tracking-wide uppercase">
                    {data.featured_alias}
                  </p>
                  <span className="font-system text-[0.7rem] tracking-wider text-cold">
                    {delta > 0 ? `+${delta}` : delta} ({total} total)
                  </span>
                </div>

                {/* Phrase reveal */}
                <div className="mb-3">
                  <p className="font-system text-[0.5rem] text-dim tracking-[0.15em] uppercase mb-1">
                    original phrase
                  </p>
                  <p className="font-literary text-[0.9rem] text-ink leading-[1.5]">
                    {data.original_phrase}
                  </p>
                </div>

                <div className="mb-3">
                  <p className="font-system text-[0.5rem] text-dim tracking-[0.15em] uppercase mb-1">
                    transformation
                  </p>
                  <p className="font-literary text-[0.85rem] text-dim italic leading-[1.5]">
                    {data.transformation}
                  </p>
                </div>

                {/* Guesses with graded judgments */}
                {guessEntries.length > 0 && (
                  <div className="flex flex-col gap-1.5">
                    {guessEntries.map(([alias, guess]) => {
                      const score = data.judgments[alias] ?? 0;
                      return (
                        <div key={alias} className="flex items-baseline gap-2 text-[0.85rem]">
                          <JudgmentIcon score={score} />
                          <span className="font-system text-[0.6rem] text-dim tracking-wide uppercase shrink-0">
                            {alias}
                          </span>
                          <span className="font-literary text-ink">{guess}</span>
                        </div>
                      );
                    })}
                  </div>
                )}

                {guessEntries.length === 0 && (
                  <p className="font-system text-[0.6rem] text-dim tracking-wider">
                    no guesses
                  </p>
                )}

                {/* Transmitter score */}
                {data.transmitter_score > 0 && (
                  <p className="mt-2 font-system text-[0.55rem] text-cold tracking-wider uppercase">
                    transmitter +{data.transmitter_score}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        <SystemText>scores updated</SystemText>
      </div>
    </Panel>
  );
}
