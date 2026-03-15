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
          <h1
            className="font-[family-name:var(--font-literary)] text-[3rem] font-normal"
            style={{ color: "var(--ink)" }}
          >
            tell
          </h1>
          <p
            className="mt-3 font-[family-name:var(--font-literary)] text-[1.1rem]"
            style={{ color: "var(--dim)" }}
          >
            a game of words and suspicion
          </p>
        </div>
        <button
          onClick={handleNewGame}
          disabled={loading}
          className="font-[family-name:var(--font-literary)] text-[1.1rem] transition-opacity hover:opacity-70 disabled:opacity-50"
          style={{ color: "var(--ink)" }}
        >
          {loading ? "creating..." : "new game \u2192"}
        </button>
      </div>
    </Stage>
  );
}
