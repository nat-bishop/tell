"use client";

import { useState, useCallback } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitBrainTestAnswer } from "@/api/actions";
import { SystemText } from "./SystemText";

export function BrainTestPhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    brainTestQuestion,
    brainTestChallengeIndex,
    brainTestChallengeType,
    brainTestOptions,
    brainTestResults,
    players,
    phase,
  } = useGameStore();

  const [submitted, setSubmitted] = useState<Record<number, number>>({});

  const handleSelect = useCallback(async (optionIndex: number) => {
    if (!gameId || !playerId) return;
    if (submitted[brainTestChallengeIndex] !== undefined) return;

    try {
      await submitBrainTestAnswer(gameId, playerId, optionIndex, brainTestChallengeIndex);
      setSubmitted((prev) => ({ ...prev, [brainTestChallengeIndex]: optionIndex }));
    } catch {
      // Silently handle — already submitted or phase changed
    }
  }, [gameId, playerId, brainTestChallengeIndex, submitted]);

  const aliasById: Record<string, string> = {};
  for (const p of players) {
    aliasById[p.id] = p.alias;
  }

  const brainTestScores = useGameStore((s) => s.brainTestScores);
  const brainTestWinnerId = useGameStore((s) => s.brainTestWinnerId);
  const brainTestWinnerAlias = useGameStore((s) => s.brainTestWinnerAlias);
  const brainTestAbilityAwarded = useGameStore((s) => s.brainTestAbilityAwarded);

  // Results view (brain_test_results phase)
  if (phase === "brain_test_results" && brainTestResults) {
    const abilityLabel = brainTestAbilityAwarded === "partial_scan"
      ? "PARTIAL SCAN"
      : brainTestAbilityAwarded === "double_vote"
        ? "DOUBLE VOTE"
        : brainTestAbilityAwarded;

    return (
      <div className="flex flex-col gap-6 pt-4">
        <p className="text-center font-system text-[0.85rem] text-dim tracking-wider uppercase">
          quick draw results
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(brainTestResults).map(([pid, answers]) => {
            const isWinner = pid === brainTestWinnerId;
            const score = brainTestScores?.[pid] ?? 0;
            return (
              <div key={pid} className={`card p-4 ${isWinner ? "border-warm/50" : ""}`}>
                <div className="flex items-baseline justify-between mb-3">
                  <p className="font-literary-sc text-[0.8rem] text-dim tracking-wide uppercase">
                    {aliasById[pid] || pid}
                  </p>
                  <span className={`font-system text-[0.7rem] tracking-wider ${
                    isWinner ? "text-warm" : "text-cold"
                  }`}>
                    {score} pt{score !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="flex flex-col gap-2">
                  {answers.map((a, i) => {
                    const selected = a.selected_index;
                    const correct = a.correct_index;
                    const isCorrect = selected === correct;
                    const selectedLabel = selected >= 0 && a.options?.[selected] ? a.options[selected] : "\u2014";
                    return (
                      <div key={i} className="flex items-baseline gap-2 text-[0.85rem]">
                        <span className={`font-system text-[0.6rem] shrink-0 tracking-wide uppercase ${
                          isCorrect ? "text-cold" : "text-warm"
                        }`}>
                          {isCorrect ? "\u2713" : "\u2717"}
                        </span>
                        <span className="font-literary text-ink">
                          {selectedLabel}
                        </span>
                      </div>
                    );
                  })}
                </div>
                {isWinner && (
                  <p className="mt-2 font-system text-[0.6rem] text-warm tracking-wider uppercase">
                    winner
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {brainTestWinnerAlias && abilityLabel && (
          <div className="animate-fade-in text-center">
            <p className="font-system text-[0.7rem] text-cold tracking-[0.15em] uppercase">
              {brainTestWinnerAlias} earns {abilityLabel}
            </p>
          </div>
        )}

        <SystemText>
          this evidence carries forward to the next vote
        </SystemText>
      </div>
    );
  }

  // Challenge view
  const alreadySubmitted = submitted[brainTestChallengeIndex] !== undefined;

  return (
    <div className="flex min-h-[50vh] flex-col items-center justify-center gap-8">
      {brainTestChallengeType && (
        <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase">
          {brainTestChallengeType.replace("_", " ")}
        </p>
      )}

      {brainTestQuestion ? (
        <p className="font-literary text-[1.2rem] text-ink text-center leading-[1.6] max-w-md">
          {brainTestQuestion}
        </p>
      ) : (
        <p className="font-system text-[0.85rem] text-dim tracking-wider uppercase">
          waiting for challenge...
        </p>
      )}

      {!spectator && brainTestQuestion && brainTestOptions.length > 0 && (
        <>
          {alreadySubmitted ? (
            <div className="w-full max-w-sm flex flex-col gap-2">
              {brainTestOptions.map((opt, i) => (
                <div
                  key={i}
                  className={`px-4 py-3 min-h-[44px] rounded font-literary text-[1rem] text-center transition-colors ${
                    i === submitted[brainTestChallengeIndex]
                      ? "bg-raised text-ink border border-cold/40"
                      : "bg-surface text-dim"
                  }`}
                >
                  {opt}
                </div>
              ))}
              <p className="mt-1 text-center font-system text-[0.65rem] text-dim tracking-wider uppercase">
                submitted
              </p>
            </div>
          ) : (
            <div className="w-full max-w-sm flex flex-col gap-2">
              {brainTestOptions.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => handleSelect(i)}
                  className="px-4 py-3 min-h-[44px] rounded font-literary text-[1rem] text-ink text-center bg-surface hover:bg-raised transition-colors border border-rule hover:border-cold/40 cursor-pointer"
                >
                  {opt}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {spectator && brainTestQuestion && (
        <SystemText>challenge in progress</SystemText>
      )}
    </div>
  );
}
