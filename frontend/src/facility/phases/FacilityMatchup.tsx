"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useGameStore, type MatchupInfo } from "@/hooks/useGameStore";
import { submitMatchupVote } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

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

export function FacilityMatchup() {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const subRoundIndex = useGameStore((s) => s.subRoundIndex);
  const subRoundPayload = useGameStore((s) => s.subRoundPayload);
  const roundPayload = useGameStore((s) => s.roundPayload);

  // Cast sub-round payload to matchup challenge data
  const matchupLeftId = (subRoundPayload?.left_player_id as string) ?? null;
  const matchupLeftAlias = (subRoundPayload?.left_alias as string) ?? null;
  const matchupLeftAnswer = (subRoundPayload?.left_answer as string) ?? null;
  const matchupRightId = (subRoundPayload?.right_player_id as string) ?? null;
  const matchupRightAlias = (subRoundPayload?.right_alias as string) ?? null;
  const matchupRightAnswer = (subRoundPayload?.right_answer as string) ?? null;

  const matchups = (roundPayload?.matchups as MatchupInfo[]) ?? null;

  const [voted, setVoted] = useState<Record<number, number>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const myVote = voted[subRoundIndex] ?? null;
  const isInPair = playerId === matchupLeftId || playerId === matchupRightId;
  const canVote = !isInPair;
  const totalMatchups = matchups?.length ?? 0;

  const handleVote = useCallback(
    (choice: number) => {
      if (!gameId || !playerId || isInPair) return;

      setVoted((prev) => ({ ...prev, [subRoundIndex]: choice }));

      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        submitMatchupVote(gameId, playerId, subRoundIndex, choice).catch(() => {});
      }, 300);
    },
    [gameId, playerId, subRoundIndex, isInPair],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  if (!matchupLeftId || !matchupRightId) {
    return (
      <Panel zone="left-screen">
        <div className="flex h-full flex-col items-center justify-center">
          <SystemText>preparing matchups...</SystemText>
        </div>
      </Panel>
    );
  }

  return (
    <>
      {/* Readout: progress */}
      <Panel zone="readout">
        <p className="font-system text-[0.65rem] text-cold tracking-[0.2em] uppercase text-center">
          {subRoundIndex + 1} / {totalMatchups}
        </p>
      </Panel>

      {/* Left screen */}
      <Panel zone="left-screen">
        <div className="flex flex-col h-full">
          {canVote ? (
            <button
              onClick={() => handleVote(0)}
              className={`h-full text-left cursor-pointer transition-all rounded-sm p-4 ${
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
            <div className={`h-full p-4 ${isInPair && playerId === matchupLeftId ? "border border-cold/30 rounded-sm" : ""}`}>
              <MatchupCard
                answer={matchupLeftAnswer}
                alias={matchupLeftAlias}
                isMyCard={playerId === matchupLeftId}
                isSelected={false}
              />
            </div>
          )}

          {/* Instruction for voters / paired players */}
          <div className="mt-auto pt-2 text-center">
            {canVote && (
              <p className="font-system text-[0.6rem] text-dim tracking-[0.15em] uppercase">
                who sounds more human?
              </p>
            )}
            {isInPair && (
              <p className="font-system text-[0.6rem] text-dim tracking-wider uppercase">
                your matchup &mdash; others are voting
              </p>
            )}
          </div>
        </div>
      </Panel>

      {/* Right screen */}
      <Panel zone="right-screen">
        {canVote ? (
          <button
            onClick={() => handleVote(1)}
            className={`h-full w-full text-left cursor-pointer transition-all rounded-sm p-4 ${
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
          <div className={`h-full p-4 ${isInPair && playerId === matchupRightId ? "border border-cold/30 rounded-sm" : ""}`}>
            <MatchupCard
              answer={matchupRightAnswer}
              alias={matchupRightAlias}
              isMyCard={playerId === matchupRightId}
              isSelected={false}
            />
          </div>
        )}
      </Panel>
    </>
  );
}
