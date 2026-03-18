"use client";

import { useGameStore, type RevealedPlayer } from "@/hooks/useGameStore";
import { NarrationInline } from "@/components/Narration";
import { createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

export function GameOver() {
  const { winnerIds, revealedPlayers, playerId, scores } = useGameStore();
  const router = useRouter();

  const handlePlayAgain = async () => {
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  const iAmWinner = winnerIds.includes(playerId ?? "");

  // Sort by score descending
  const sorted = [...(revealedPlayers || [])].sort(
    (a, b) => (b.score ?? 0) - (a.score ?? 0),
  );

  const totalPlayers = sorted.length;
  const topScore = sorted[0]?.score ?? 0;

  // Headline based on score
  let headline: string;
  if (winnerIds.length === 0) {
    headline = "GAME OVER";
  } else if (iAmWinner) {
    headline = "YOU WIN";
  } else if (winnerIds.length === 1) {
    const winnerPlayer = revealedPlayers?.find(p => p.id === winnerIds[0]);
    headline = `${winnerPlayer?.alias ?? "UNKNOWN"} WINS`;
  } else {
    headline = "TIE";
  }

  // Check if the winner is AI for dramatic effect
  const winnerPlayer = winnerIds.length === 1
    ? revealedPlayers?.find(p => p.id === winnerIds[0])
    : null;
  const isMachineWin = winnerPlayer?.role === "ai";

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
      <p
        className="animate-headline-reveal font-system text-[1.3rem] text-ink tracking-[0.15em] uppercase"
        style={{
          textShadow: isMachineWin
            ? '0 0 30px var(--cold), 0 0 60px rgba(91, 143, 185, 0.2)'
            : '0 0 30px var(--warm), 0 0 60px rgba(224, 122, 95, 0.2)',
        }}
      >
        {headline}
      </p>

      {/* Scoreboard with role reveal */}
      <div className="flex flex-col gap-3 w-full max-w-md">
        {sorted.map((p, i) => {
          const isWinner = winnerIds.includes(p.id);
          const playerScore = p.score ?? scores[p.id] ?? 0;
          return (
            <div
              key={p.id}
              className="flex items-center gap-4 min-h-[44px] animate-fade-in"
              style={{ animationDelay: `${(i * 400) + 1000}ms` }}
            >
              {/* Rank */}
              <span className="font-system text-[0.7rem] text-dim w-6 text-right">
                {i + 1}.
              </span>

              {/* Alias */}
              <span
                className={`w-28 font-system text-[0.8rem] tracking-[0.1em] uppercase ${
                  isWinner ? 'text-warm' : 'text-ink'
                }`}
              >
                {p.alias}
              </span>

              {/* Role */}
              <span
                className={`font-system text-[0.8rem] tracking-wider uppercase ${
                  p.role === 'human' ? 'text-warm glow-warm' : 'text-cold glow-cold'
                }`}
              >
                {p.role}
              </span>

              {/* Score */}
              <span className={`ml-auto font-system text-[0.8rem] tracking-wider ${
                isWinner ? 'text-warm' : 'text-ink'
              }`}>
                {playerScore} pt{playerScore !== 1 ? "s" : ""}
              </span>
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
