"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { usePlayerColors } from "./usePlayerColors";
import { endGame, skipStep, createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

export function HudPanel() {
  const { players, phase, roundNumber, scores, isHost, gameId, playerId } = useGameStore();
  const colorMap = usePlayerColors();
  const router = useRouter();

  if (phase === "lobby" || phase === "game_over") return null;

  const handleSkip = async () => {
    if (!gameId || !playerId) return;
    await skipStep(gameId, playerId);
  };

  const handleEnd = async () => {
    if (!gameId || !playerId) return;
    await endGame(gameId, playerId);
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  return (
    <div
      className="fixed top-[6px] left-0 right-0 z-40 flex items-center justify-center gap-4 py-1.5 px-4"
      style={{
        background: "linear-gradient(180deg, rgba(0,0,0,0.3) 0%, transparent 100%)",
      }}
    >
      <span className="font-system text-[0.6rem] text-cold tracking-widest uppercase">
        r{roundNumber}
      </span>

      {players.map((p) => {
        const playerScore = scores[p.id] ?? 0;
        const color = colorMap[p.id] ?? "var(--cold)";
        return (
          <div key={p.id} className="flex items-center gap-1.5">
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: color, boxShadow: `0 0 6px ${color}` }}
            />
            <span className="font-system text-[0.6rem] tracking-[0.1em] uppercase text-ink">
              {p.alias}
            </span>
            {playerScore > 0 && (
              <span className="font-system text-[0.55rem] text-warm tracking-wider">
                {playerScore}
              </span>
            )}
          </div>
        );
      })}

      {isHost && (
        <div className="fixed top-[6px] right-3 z-40 flex items-center gap-3">
          <button
            onClick={handleSkip}
            className="font-system text-[0.6rem] text-dim tracking-wide transition-all hover:text-cold"
          >
            next
          </button>
          <button
            onClick={handleEnd}
            className="font-system text-[0.6rem] text-dim tracking-wide transition-all hover:text-warm"
          >
            end
          </button>
        </div>
      )}
    </div>
  );
}
