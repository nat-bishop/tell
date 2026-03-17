"use client";

import { useState, useRef, useCallback } from "react";
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
    brainTestResults,
    players,
    phase,
  } = useGameStore();

  const [answer, setAnswer] = useState("");
  const [submitted, setSubmitted] = useState<Record<number, string>>({});
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(async () => {
    if (!gameId || !playerId || !answer.trim()) return;
    if (submitted[brainTestChallengeIndex]) return;

    try {
      await submitBrainTestAnswer(gameId, playerId, answer.trim(), brainTestChallengeIndex);
      setSubmitted((prev) => ({ ...prev, [brainTestChallengeIndex]: answer.trim() }));
      setAnswer("");
    } catch {
      // Silently handle — already submitted or phase changed
    }
  }, [gameId, playerId, answer, brainTestChallengeIndex, submitted]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const aliasById: Record<string, string> = {};
  for (const p of players) {
    aliasById[p.id] = p.alias;
  }

  // Results view (brain_test_results phase)
  if (phase === "brain_test_results" && brainTestResults) {
    return (
      <div className="flex flex-col gap-6 pt-4">
        <p className="text-center font-system text-[0.85rem] text-dim tracking-wider uppercase">
          brain test results
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(brainTestResults).map(([pid, answers]) => (
            <div key={pid} className="card p-4">
              <p className="font-literary-sc text-[0.8rem] text-dim tracking-wide uppercase mb-3">
                {aliasById[pid] || pid}
              </p>
              <div className="flex flex-col gap-2">
                {answers.map((a, i) => (
                  <div key={i} className="flex items-baseline gap-2 text-[0.85rem]">
                    <span className="font-system text-[0.6rem] text-cold shrink-0 tracking-wide uppercase">
                      {a.challenge_type}
                    </span>
                    <span className="font-literary text-ink">
                      {a.answer || "\u2014"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

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

      {!spectator && brainTestQuestion && (
        <>
          {alreadySubmitted ? (
            <div className="submitted-panel text-center">
              <p className="font-literary text-[1rem] text-ink">
                {submitted[brainTestChallengeIndex]}
              </p>
              <p className="mt-2 font-system text-[0.65rem] text-dim tracking-wider uppercase">
                submitted
              </p>
            </div>
          ) : (
            <div className="w-full max-w-sm">
              <input
                ref={inputRef}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full border-b bg-transparent py-2 min-h-[44px] text-center font-literary text-[1.1rem] text-ink outline-none border-rule"
                placeholder="your answer"
                maxLength={100}
                autoFocus
              />
              <button
                onClick={handleSubmit}
                disabled={!answer.trim()}
                className="btn-action mt-4 w-full"
              >
                submit
              </button>
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
