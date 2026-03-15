"use client";

import { useGameStore } from "@/hooks/useGameStore";
import { createGame } from "@/api/actions";
import { useRouter } from "next/navigation";

export function GameOver() {
  const { winner, revealedPlayers } = useGameStore();
  const router = useRouter();

  const handlePlayAgain = async () => {
    const res = await createGame();
    router.push(`/game/${res.game_id}`);
  };

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
      <p
        className="animate-fade-in font-[family-name:var(--font-literary)] text-[1.5rem]"
        style={{ color: "var(--ink)" }}
      >
        {winner === "ai" ? "the machines win." : "humanity survives."}
      </p>

      <div className="flex flex-col gap-3">
        {revealedPlayers?.map(
          (p: {
            id: string;
            alias: string;
            role: string;
            is_alive: boolean;
            eliminated_round?: number;
          }) => (
            <div
              key={p.id}
              className="flex items-center gap-4 animate-fade-in"
            >
              <span
                className="w-24 font-[family-name:var(--font-literary-sc)] text-[0.9rem] tracking-[0.08em]"
                style={{ color: p.is_alive ? "var(--ink)" : "var(--dim)" }}
              >
                {p.alias}
              </span>
              <span
                className="font-[family-name:var(--font-literary)] text-[1rem]"
                style={{
                  color: p.role === "human" ? "var(--warm)" : "var(--dim)",
                }}
              >
                {p.role}
              </span>
              {!p.is_alive && (
                <span
                  className="font-[family-name:var(--font-system)] text-[0.7rem]"
                  style={{ color: "var(--dim)" }}
                >
                  (voted off, round {p.eliminated_round})
                </span>
              )}
            </div>
          ),
        )}
      </div>

      <button
        onClick={handlePlayAgain}
        className="font-[family-name:var(--font-literary)] text-[1.1rem] transition-opacity hover:opacity-70"
        style={{ color: "var(--ink)" }}
      >
        play again &rarr;
      </button>
    </div>
  );
}
