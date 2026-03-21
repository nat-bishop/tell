"use client";

import { useState, useCallback, useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitBrainTestAnswer } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

export function FacilityBrainTest() {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const subRoundPayload = useGameStore((s) => s.subRoundPayload);
  const roundResults = useGameStore((s) => s.roundResults);
  const roundScores = useGameStore((s) => s.roundScores);
  const players = useGameStore((s) => s.players);
  const scores = useGameStore((s) => s.scores);

  // Extract brain test fields from generic payload (guard round_type)
  const isBrainTest = subRoundPayload?.round_type === "brain_test";
  const challengeIndex = isBrainTest ? subRoundPayload.challenge_index : 0;
  const challengeType = isBrainTest ? subRoundPayload.challenge_type : null;
  const question = isBrainTest ? subRoundPayload.question : null;
  const options = isBrainTest ? subRoundPayload.options : [];

  const [submitted, setSubmitted] = useState<Record<number, number>>({});
  const [pendingIndex, setPendingIndex] = useState<Record<number, number>>({});

  const handleSelect = useCallback(
    async (optionIndex: number) => {
      if (!gameId || !playerId) return;
      if (submitted[challengeIndex] !== undefined) return;
      if (pendingIndex[challengeIndex] !== undefined) return;

      setPendingIndex((prev) => ({ ...prev, [challengeIndex]: optionIndex }));

      try {
        await submitBrainTestAnswer(gameId, playerId, optionIndex, challengeIndex);
        setSubmitted((prev) => ({ ...prev, [challengeIndex]: optionIndex }));
      } catch {
        // API failed — unlock selection
        setPendingIndex((prev) => {
          const next = { ...prev };
          delete next[challengeIndex];
          return next;
        });
      }
    },
    [gameId, playerId, challengeIndex, submitted, pendingIndex],
  );

  const aliasById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const p of players) map[p.id] = p.alias;
    return map;
  }, [players]);

  // Results view
  if (roundResults && roundResults.round_type === "brain_test") {
    const brainTestResults = roundResults.results;
    const sortedEntries = Object.entries(brainTestResults).sort(([aId], [bId]) => {
      const aScore = roundScores?.[aId] ?? 0;
      const bScore = roundScores?.[bId] ?? 0;
      return bScore - aScore;
    });

    return (
      <Panel zone="full-screen">
        <div className="flex flex-col gap-6 pt-4">
          <p className="text-center font-system text-[0.85rem] text-dim tracking-wider uppercase">
            quick draw results
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {sortedEntries.map(([pid, answers]) => {
              const score = roundScores?.[pid] ?? 0;
              const runningScore = scores[pid] ?? 0;
              return (
                <div key={pid} className="card p-4">
                  <div className="flex items-baseline justify-between mb-3">
                    <p className="font-literary-sc text-[0.8rem] text-dim tracking-wide uppercase">
                      {aliasById[pid] || pid}
                    </p>
                    <span className="font-system text-[0.7rem] tracking-wider text-cold">
                      +{score} ({runningScore} total)
                    </span>
                  </div>
                  <div className="flex flex-col gap-2">
                    {answers.map((a, i) => {
                      const selected = a.selected_index;
                      const correct = a.correct_index;
                      const isCorrect = selected === correct;
                      const selectedLabel =
                        selected >= 0 && a.options?.[selected] ? a.options[selected] : "\u2014";
                      return (
                        <div key={i} className="flex items-baseline gap-2 text-[0.85rem]">
                          <span
                            className={`font-system text-[0.6rem] shrink-0 tracking-wide uppercase ${
                              isCorrect ? "text-cold" : "text-warm"
                            }`}
                          >
                            {isCorrect ? "\u2713" : "\u2717"}
                          </span>
                          <span className="font-literary text-ink">{selectedLabel}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>

          <SystemText>scores updated</SystemText>
        </div>
      </Panel>
    );
  }

  // Challenge view
  const selectedIndex = pendingIndex[challengeIndex] ?? submitted[challengeIndex] ?? null;
  const isLocked = selectedIndex !== null;

  return (
    <>
      {/* Main screen — challenge type + question */}
      <Panel zone="main-screen">
        <div className="flex flex-col items-center justify-center h-full gap-4">
          {challengeType && (
            <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase">
              {challengeType.replace("_", " ")}
            </p>
          )}

          {question ? (
            <p className="font-literary text-[1.2rem] text-ink text-center leading-[1.6] max-w-md">
              {question}
            </p>
          ) : (
            <p className="font-system text-[0.85rem] text-dim tracking-wider uppercase">
              waiting for challenge...
            </p>
          )}
        </div>
      </Panel>

      {/* Center area — options */}
      <Panel zone="center-area">
        <div className="flex flex-col items-center justify-center h-full gap-2">
          {question && options.length > 0 && (
            <div className="w-full max-w-sm flex flex-col gap-2">
              {options.map((opt, i) => {
                const isSelected = i === selectedIndex;
                return (
                  <button
                    key={i}
                    onClick={() => handleSelect(i)}
                    disabled={isLocked}
                    className={`px-4 py-3 min-h-[44px] rounded font-literary text-[1rem] text-center transition-all cursor-pointer ${
                      isSelected
                        ? "card-highlighted animate-vote-select text-ink"
                        : isLocked
                          ? "card opacity-40 text-dim pointer-events-none"
                          : "card card-interactive text-ink"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
              {isLocked && (
                <p className="mt-1 text-center font-system text-[0.65rem] text-dim tracking-wider uppercase animate-fade-in">
                  submitted
                </p>
              )}
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}
