"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { submitVote } from "@/api/actions";
import { Panel } from "@/facility/Panel";
import { SystemText } from "@/components/SystemText";

function AnswerCard({
  answer,
  alias,
  isOwn,
  isSelected,
}: {
  answer: string;
  alias: string;
  isOwn: boolean;
  isSelected: boolean;
}) {
  return (
    <div className="flex flex-col h-full min-h-[80px]">
      <div className="font-literary text-[0.95rem] leading-[1.6] text-ink">
        {answer}
      </div>
      <div className="mt-auto pt-2 border-t border-rule flex items-baseline justify-between">
        <div
          className={`font-system text-[0.65rem] tracking-[0.1em] uppercase ${
            isSelected ? "text-warm" : "text-dim"
          }`}
        >
          {alias}
        </div>
        {isOwn && (
          <div className="font-system text-[0.55rem] text-cold tracking-wider uppercase">
            your answer
          </div>
        )}
        {isSelected && (
          <div className="font-system text-[0.55rem] text-warm tracking-wider uppercase">
            voted
          </div>
        )}
      </div>
    </div>
  );
}

export function FacilityVote() {
  const gameId = useGameStore((s) => s.gameId);
  const playerId = useGameStore((s) => s.playerId);
  const answers = useGameStore((s) => s.answers);
  const players = useGameStore((s) => s.players);
  const promptText = useGameStore((s) => s.promptText);
  const voteCount = useGameStore((s) => s.voteCount);
  const votedForId = useGameStore((s) => s.votedForId);

  const [localVote, setLocalVote] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Sync from server on reconnect
  useEffect(() => {
    if (votedForId) setLocalVote(votedForId);
  }, [votedForId]);

  const handleVote = useCallback(
    (targetId: string) => {
      if (!gameId || !playerId || targetId === playerId) return;

      const newVote = localVote === targetId ? null : targetId;
      setLocalVote(newVote);

      if (debounceRef.current) clearTimeout(debounceRef.current);
      if (newVote) {
        debounceRef.current = setTimeout(() => {
          if (useGameStore.getState().component !== "task_active") return;
          submitVote(gameId, playerId, newVote).catch(() => {});
        }, 300);
      }
    },
    [gameId, playerId, localVote],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const aliasMap = useMemo(
    () => Object.fromEntries(players.map((p) => [p.id, p.alias])),
    [players],
  );
  const answerEntries = Object.entries(answers);
  const totalPlayers = players.length;

  return (
    <Panel zone="full-screen">
      <div className="flex flex-col h-full gap-4 p-2">
        {/* Header */}
        <div className="flex items-center justify-between">
          <p className="font-literary text-[0.9rem] italic text-dim max-w-[60%] line-clamp-2">
            {promptText}
          </p>
          <SystemText>
            {voteCount} / {totalPlayers} voted
          </SystemText>
        </div>

        <p className="font-system text-[0.6rem] text-cold tracking-[0.2em] uppercase text-center">
          who sounds most human?
        </p>

        {/* Gallery grid */}
        <div className="grid grid-cols-2 gap-3 flex-1 overflow-y-auto">
          {answerEntries.map(([pid, answer]) => {
            const isOwn = pid === playerId;
            const isSelected = localVote === pid;
            const alias = aliasMap[pid] || pid;

            if (isOwn) {
              return (
                <div
                  key={pid}
                  className="border border-cold/20 rounded-sm p-3 opacity-70"
                >
                  <AnswerCard
                    answer={answer}
                    alias={alias}
                    isOwn
                    isSelected={false}
                  />
                </div>
              );
            }

            return (
              <button
                key={pid}
                onClick={() => handleVote(pid)}
                className={`text-left cursor-pointer transition-all rounded-sm p-3 ${
                  isSelected
                    ? "card-highlighted animate-vote-select"
                    : "card-interactive"
                }`}
              >
                <AnswerCard
                  answer={answer}
                  alias={alias}
                  isOwn={false}
                  isSelected={isSelected}
                />
              </button>
            );
          })}
        </div>
      </div>
    </Panel>
  );
}
