"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createGame } from "@/api/actions";
import { Stage } from "@/components/Stage";
import { SystemText } from "@/components/SystemText";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handlePlay = () => {
    router.push("/queue");
  };

  const handlePrivateGame = async () => {
    setLoading(true);
    try {
      const res = await createGame();
      router.push(`/game/${res.game_id}`);
    } catch {
      setLoading(false);
    }
  };

  return (
    <Stage>
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-12">
        <div className="text-center">
          <h1
            className="font-system text-[3.5rem] font-normal text-ink tracking-[0.2em] uppercase animate-glitch"
            style={{ textShadow: '0 0 60px var(--cold-glow), 0 0 120px rgba(91, 143, 185, 0.08)' }}
          >
            tell
          </h1>
          <p className="mt-4 font-system text-[0.8rem] text-dim tracking-[0.15em]">
            a reverse turing test
          </p>
        </div>

        <div className="flex flex-col items-center gap-4">
          <button
            onClick={handlePlay}
            className="btn-action text-[0.9rem]"
          >
            enter test &rarr;
          </button>
          <button
            onClick={handlePrivateGame}
            disabled={loading}
            className="font-system text-[0.75rem] text-dim tracking-wide transition-all hover:text-cold disabled:opacity-50"
          >
            {loading ? "creating..." : "isolated examination"}
          </button>
        </div>

        <SystemText>
          enter test finds a game automatically &mdash; isolated examination
          creates a link to share
        </SystemText>
      </div>
    </Stage>
  );
}
