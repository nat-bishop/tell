"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createGame } from "@/api/actions";
import { Stage } from "@/components/Stage";

export default function Home() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const handleNewGame = async () => {
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
          <h1 className="font-literary text-[3rem] font-normal text-ink">
            tell
          </h1>
          <p className="mt-3 font-literary text-[1.1rem] text-dim">
            a game of words and suspicion
          </p>
        </div>
        <button
          onClick={handleNewGame}
          disabled={loading}
          className="font-literary text-[1.1rem] text-ink transition-opacity hover:opacity-70 disabled:opacity-50"
        >
          {loading ? "creating..." : "new game \u2192"}
        </button>
      </div>
    </Stage>
  );
}
