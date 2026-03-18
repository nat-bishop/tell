"use client";

import { useGameStore, type RevealedPlayer } from "@/hooks/useGameStore";
import { NarrationInline } from "@/components/Narration";
import { createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

export function GameOver() {
  const { winner, winnerIds, revealedPlayers, playerId } = useGameStore();
  const router = useRouter();

  const handlePlayAgain = async () => {
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  const isMachineWin = winner === "ai";
  const iAmWinner = winnerIds.includes(playerId ?? "");

  // Sort: survivors (winners) first, then eliminated by round
  const sorted = [...(revealedPlayers || [])].sort(
    (a, b) => {
      if (a.is_alive && !b.is_alive) return -1;
      if (!a.is_alive && b.is_alive) return 1;
      if (!a.is_alive && !b.is_alive)
        return (a.eliminated_round || 0) - (b.eliminated_round || 0);
      return 0;
    },
  );

  const totalPlayers = sorted.length;

  // Headline
  let headline: string;
  if (isMachineWin) {
    headline = "THE MACHINES WIN";
  } else if (winnerIds.length === 1) {
    const winnerPlayer = revealedPlayers?.find(p => p.id === winnerIds[0]);
    headline = iAmWinner ? "YOU SURVIVE" : `${winnerPlayer?.alias ?? "UNKNOWN"} SURVIVES`;
  } else {
    headline = iAmWinner ? "YOU SURVIVE" : "SURVIVORS";
  }

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
      <p
        className="animate-elimination-reveal font-system text-[1.3rem] text-ink tracking-[0.15em] uppercase"
        style={{
          textShadow: isMachineWin
            ? '0 0 30px var(--cold), 0 0 60px rgba(91, 143, 185, 0.2)'
            : '0 0 30px var(--warm), 0 0 60px rgba(224, 122, 95, 0.2)',
        }}
      >
        {headline}
      </p>

      <div className="flex flex-col gap-3">
        {sorted.map((p, i) => {
          const isWinner = winnerIds.includes(p.id);
          return (
            <div
              key={p.id}
              className="flex items-center gap-4 min-h-[44px] animate-fade-in"
              style={{ animationDelay: `${(i * 400) + 1000}ms` }}
            >
              <span
                className={`w-28 font-system text-[0.8rem] tracking-[0.1em] uppercase ${
                  isWinner ? 'text-warm' : p.is_alive ? 'text-ink' : 'text-dim line-through'
                }`}
              >
                {p.alias}
              </span>
              <span
                className={`font-system text-[0.8rem] tracking-wider uppercase ${
                  p.role === 'human' ? 'text-warm glow-warm' : 'text-cold glow-cold'
                }`}
              >
                {p.role}
              </span>
              {!p.is_alive && (
                <span className="font-system text-[0.65rem] text-dim tracking-wide">
                  R{p.eliminated_round}
                </span>
              )}
              {isWinner && (
                <span className="font-system text-[0.65rem] text-warm tracking-wide uppercase">
                  survived
                </span>
              )}
            </div>
          );
        })}
      </div>

      <div
        className="animate-fade-in"
        style={{ animationDelay: `${(totalPlayers * 400) + 1500}ms` }}
      >
        <NarrationInline />
      </div>

      <button
        onClick={handlePlayAgain}
        className="btn-action animate-fade-in"
        style={{ animationDelay: `${(totalPlayers * 400) + 2500}ms` }}
      >
        play again &rarr;
      </button>
    </div>
  );
}
