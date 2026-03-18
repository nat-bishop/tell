"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitMatchupVote } from "@/api/actions";
import { SystemText } from "./SystemText";

export function MatchupPhase({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    matchupIndex,
    matchupLeftId,
    matchupLeftAlias,
    matchupLeftAnswer,
    matchupRightId,
    matchupRightAlias,
    matchupRightAnswer,
    matchupPromptText,
    matchups,
  } = useGameStore();

  const [voted, setVoted] = useState<Record<number, number>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Reset vote state when a new matchup challenge arrives
  const prevIndexRef = useRef(matchupIndex);
  useEffect(() => {
    if (matchupIndex !== prevIndexRef.current) {
      prevIndexRef.current = matchupIndex;
    }
  }, [matchupIndex]);

  const myVote = voted[matchupIndex] ?? null;

  // Am I in this matchup pair?
  const isInPair = playerId === matchupLeftId || playerId === matchupRightId;
  const canVote = !spectator && !isInPair;

  const totalMatchups = matchups?.length ?? 0;

  const handleVote = useCallback(
    (choice: number) => {
      if (!gameId || !playerId || isInPair || spectator) return;

      setVoted((prev) => ({ ...prev, [matchupIndex]: choice }));
      useGameStore.setState({ matchupMyVote: choice });

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        submitMatchupVote(gameId, playerId, matchupIndex, choice).catch(() => {});
      }, 300);
    },
    [gameId, playerId, matchupIndex, isInPair, spectator],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Waiting for first challenge
  if (!matchupLeftId || !matchupRightId) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-4">
        <SystemText>preparing matchups...</SystemText>
      </div>
    );
  }

  const myAlias = playerId === matchupLeftId
    ? matchupLeftAlias
    : playerId === matchupRightId
      ? matchupRightAlias
      : null;

  return (
    <div className="flex flex-col items-center gap-6 pt-4">
      {/* Progress indicator */}
      <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase">
        matchup {matchupIndex + 1} of {totalMatchups}
      </p>

      {/* Prompt */}
      {matchupPromptText && (
        <p className="text-center font-literary text-[1rem] italic leading-[1.6] text-dim max-w-lg">
          {matchupPromptText}
        </p>
      )}

      {/* 1v1 Split */}
      <div className="w-full grid grid-cols-2 gap-3" key={matchupIndex}>
        {/* Left card */}
        {canVote ? (
          <button
            onClick={() => handleVote(0)}
            className={`animate-fade-in card p-5 text-left cursor-pointer transition-all ${
              myVote === 0 ? "card-highlighted animate-vote-select" : "card-interactive"
            }`}
          >
            <MatchupCard
              answer={matchupLeftAnswer}
              alias={matchupLeftAlias}
              isMyCard={false}
              isSelected={myVote === 0}
            />
          </button>
        ) : (
          <div className={`animate-fade-in card p-5 ${isInPair && playerId === matchupLeftId ? "border-cold/30" : ""}`}>
            <MatchupCard
              answer={matchupLeftAnswer}
              alias={matchupLeftAlias}
              isMyCard={playerId === matchupLeftId}
              isSelected={false}
            />
          </div>
        )}

        {/* Right card */}
        {canVote ? (
          <button
            onClick={() => handleVote(1)}
            className={`animate-fade-in card p-5 text-left cursor-pointer transition-all ${
              myVote === 1 ? "card-highlighted animate-vote-select" : "card-interactive"
            }`}
          >
            <MatchupCard
              answer={matchupRightAnswer}
              alias={matchupRightAlias}
              isMyCard={false}
              isSelected={myVote === 1}
            />
          </button>
        ) : (
          <div className={`animate-fade-in card p-5 ${isInPair && playerId === matchupRightId ? "border-cold/30" : ""}`}>
            <MatchupCard
              answer={matchupRightAnswer}
              alias={matchupRightAlias}
              isMyCard={playerId === matchupRightId}
              isSelected={false}
            />
          </div>
        )}
      </div>

      {/* Instruction text */}
      {canVote && (
        <p className="font-system text-[0.7rem] text-dim tracking-[0.15em] uppercase">
          who sounds more human?
        </p>
      )}
      {isInPair && (
        <p className="font-system text-[0.65rem] text-dim tracking-wider uppercase">
          your matchup &mdash; others are voting
        </p>
      )}
      {spectator && (
        <SystemText>matchup in progress</SystemText>
      )}
    </div>
  );
}

function MatchupCard({
  answer,
  alias,
  isMyCard,
  isSelected,
}: {
  answer: string | null;
  alias: string | null;
  isMyCard: boolean;
  isSelected: boolean;
}) {
  return (
    <div className="flex flex-col h-full min-h-[120px]">
      {answer ? (
        <div className="font-literary text-[1.05rem] leading-[1.6] text-ink">
          {answer}
        </div>
      ) : (
        <div className="font-system text-[0.85rem] text-dim tracking-wide">
          NO RESPONSE
        </div>
      )}

      <div className="mt-auto pt-3 border-t border-rule flex items-baseline justify-between">
        <div
          className={`font-system text-[0.75rem] tracking-[0.1em] uppercase ${
            isSelected ? "text-warm" : "text-dim"
          }`}
        >
          {alias}
        </div>
        {isMyCard && (
          <div className="font-system text-[0.6rem] text-cold tracking-wider uppercase">
            your answer
          </div>
        )}
        {isSelected && (
          <div className="font-system text-[0.6rem] text-warm tracking-wider uppercase">
            voted
          </div>
        )}
      </div>
    </div>
  );
}
