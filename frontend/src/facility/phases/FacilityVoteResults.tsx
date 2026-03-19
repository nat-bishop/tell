"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

export function FacilityVoteResults() {
  const players = useGameStore((s) => s.players);
  const voteResults = useGameStore((s) => s.voteResults);
  const scores = useGameStore((s) => s.scores);

  const voteCounts = voteResults?.vote_counts || {};

  // Sort players by votes received (descending)
  const sorted = [...players].sort(
    (a, b) => (voteCounts[b.id] ?? 0) - (voteCounts[a.id] ?? 0),
  );
  const maxVotes = Math.max(0, ...Object.values(voteCounts));

  return (
    <Panel zone="full-screen">
      <div className="flex min-h-full flex-col items-center justify-center gap-6">
        <p className="font-system text-[1rem] text-ink tracking-[0.15em] uppercase">
          DETECTION RESULTS
        </p>

        <div className="flex flex-col gap-3 w-full max-w-md">
          {sorted.map((p, i) => {
            const votes = voteCounts[p.id] ?? 0;
            const playerScore = scores[p.id] ?? 0;
            const blendedIn = votes === 0;
            const mostVotes = votes > 0 && votes === maxVotes;

            return (
              <div
                key={p.id}
                className="flex items-center gap-4 min-h-[40px] animate-fade-in"
                style={{ animationDelay: `${i * 200}ms` }}
              >
                <span className="w-24 font-system text-[0.8rem] tracking-[0.1em] uppercase text-ink">
                  {p.alias}
                </span>

                <span
                  className={`font-system text-[0.8rem] tracking-wider ${
                    votes > 0 ? "text-warm" : "text-dim"
                  }`}
                >
                  {votes > 0 ? `-${votes}` : "0"}
                </span>

                <span className="font-system text-[0.6rem] tracking-wider uppercase text-dim">
                  {blendedIn && "blended in"}
                  {mostVotes && "detected"}
                </span>

                <span className="ml-auto font-system text-[0.75rem] tracking-wider text-dim">
                  {playerScore} pt{playerScore !== 1 && playerScore !== -1 ? "s" : ""}
                </span>
              </div>
            );
          })}
        </div>

        <SystemText>next round starting...</SystemText>
      </div>
    </Panel>
  );
}
