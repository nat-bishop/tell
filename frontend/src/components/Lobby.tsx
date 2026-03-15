"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { startGame } from "@/api/actions";
import { SystemText } from "./SystemText";

export function Lobby() {
  const { gameId, playerId, players, isHost } = useGameStore();
  const humanCount = players.filter((p) => p.is_alive).length;
  const canStart = humanCount >= 2;

  const handleStart = async () => {
    if (gameId && playerId) {
      await startGame(gameId, playerId, 2);
    }
  };

  return (
    <div className="flex flex-col items-center gap-8 pt-16">
      <h1
        className="font-[family-name:var(--font-literary)] text-[3rem] font-normal"
        style={{ color: "var(--ink)" }}
      >
        tell
      </h1>

      <div className="flex flex-col items-center gap-3">
        {players.map((p) => (
          <div key={p.id} className="flex items-center gap-2 animate-fade-in">
            <span
              className="font-[family-name:var(--font-literary-sc)] text-[1rem] tracking-[0.08em]"
              style={{ color: p.is_connected ? "var(--ink)" : "var(--dim)" }}
            >
              {p.alias}
            </span>
            {p.is_connected && (
              <span style={{ color: "var(--dim)" }}>&middot;</span>
            )}
          </div>
        ))}
      </div>

      <SystemText>{humanCount} connected</SystemText>

      {isHost && (
        <button
          onClick={handleStart}
          disabled={!canStart}
          className="font-[family-name:var(--font-literary)] text-[1.1rem] py-2 px-4 transition-opacity disabled:opacity-30"
          style={{ color: "var(--ink)" }}
        >
          begin
        </button>
      )}

      {!isHost && <SystemText>waiting for host to begin</SystemText>}

      <SystemText>share this link to invite players</SystemText>
    </div>
  );
}
