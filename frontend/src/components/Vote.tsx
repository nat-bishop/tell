"use client";

import { useState } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { useAnswerEntries } from "@/hooks/useAnswerEntries";
import { castVote } from "@/api/actions";
import { Dialogue } from "./Dialogue";
import { SystemText } from "./SystemText";

export function Vote({ spectator = false }: { spectator?: boolean }) {
  const {
    gameId,
    playerId,
    players,
    messages,
    voteCount,
    voteTotalCount,
    myVote,
  } = useGameStore();
  const answerEntries = useAnswerEntries();
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

  return (
    <div className="chat-scroll flex flex-col gap-6">
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
          <hr className="divider" />
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

      <hr className="divider" />

      {spectator ? (
        <div className="flex items-center justify-between">
          <span className="font-literary text-[1.1rem] text-dim">
            voting in progress
          </span>
          <SystemText>
            {voteCount} of {voteTotalCount} voted
          </SystemText>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          <span className="font-literary text-[1.1rem] text-ink">
            who is human?
          </span>

          <div className="flex flex-col gap-2">
            {alivePlayers.map((p) => (
              <button
                key={p.id}
                onClick={() => !hasVoted && setSelected(p.id)}
                disabled={hasVoted}
                className="flex items-center py-3 pl-3 text-left transition-all min-h-[44px]"
                style={{
                  borderLeft:
                    selected === p.id
                      ? "3px solid var(--warm)"
                      : "3px solid transparent",
                }}
              >
                <span
                  className={`font-literary-sc text-[0.95rem] tracking-[0.08em] ${selected === p.id ? 'text-warm' : 'text-ink'}`}
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
                className="font-literary text-[1rem] text-ink transition-opacity hover:opacity-70"
              >
                confirm &rarr;
              </button>
            )}
            {hasVoted && <SystemText>vote cast</SystemText>}
          </div>
        </div>
      )}
    </div>
  );
}
