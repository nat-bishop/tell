"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { castVote } from "@/api/actions";
import { Dialogue } from "./Dialogue";
import { SystemText } from "./SystemText";

export function Vote() {
  const {
    gameId,
    playerId,
    players,
    answers,
    messages,
    voteCount,
    voteTotalCount,
    myVote,
  } = useGameStore();
  const [selected, setSelected] = useState<string | null>(null);
  const [voted, setVoted] = useState(false);

  const hasVoted = voted || myVote !== null;
  const alivePlayers = players.filter((p) => p.is_alive);

  const handleConfirm = async () => {
    if (gameId && playerId && selected && !hasVoted) {
      setVoted(true);
      await castVote(gameId, playerId, selected);
    }
  };

  const answerEntries = Object.entries(answers).map(([pid, text]) => {
    const player = players.find((p) => p.id === pid);
    return { alias: player?.alias || "???", text };
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="max-h-[40vh] space-y-7 overflow-y-auto">
        {answerEntries.map((entry, i) => (
          <Dialogue
            key={`answer-${i}`}
            alias={entry.alias}
            text={entry.text}
            animate={false}
          />
        ))}
        {messages.length > 0 && (
          <div
            className="my-6 mx-auto w-12"
            style={{ borderTop: "1px solid var(--rule)" }}
          />
        )}
        {messages.map((msg, i) => (
          <Dialogue
            key={`msg-${i}`}
            alias={msg.player_alias}
            text={msg.text}
            animate={false}
          />
        ))}
      </div>

      <div
        className="mx-auto w-12"
        style={{ borderTop: "1px solid var(--rule)" }}
      />

      <div className="flex flex-col gap-4">
        <span
          className="font-[family-name:var(--font-literary)] text-[1.1rem]"
          style={{ color: "var(--ink)" }}
        >
          who is human?
        </span>

        <div className="flex flex-col gap-2">
          {alivePlayers.map((p) => (
            <button
              key={p.id}
              onClick={() => !hasVoted && setSelected(p.id)}
              disabled={hasVoted}
              className="flex items-center py-2 pl-3 text-left transition-all"
              style={{
                borderLeft:
                  selected === p.id
                    ? "3px solid var(--warm)"
                    : "3px solid transparent",
              }}
            >
              <span
                className="font-[family-name:var(--font-literary-sc)] text-[0.95rem] tracking-[0.08em]"
                style={{
                  color: selected === p.id ? "var(--warm)" : "var(--ink)",
                }}
              >
                {p.alias}
              </span>
            </button>
          ))}
        </div>

        <div className="flex items-center justify-between">
          <SystemText>
            {voteCount} of {voteTotalCount} voted
          </SystemText>
          {!hasVoted && selected && (
            <button
              onClick={handleConfirm}
              className="font-[family-name:var(--font-literary)] text-[1rem] transition-opacity hover:opacity-70"
              style={{ color: "var(--ink)" }}
            >
              confirm &rarr;
            </button>
          )}
          {hasVoted && <SystemText>vote cast</SystemText>}
        </div>
      </div>
    </div>
  );
}
