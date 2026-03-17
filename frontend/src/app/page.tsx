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
          <h1 className="font-literary text-[3rem] font-normal text-ink">
            tell
          </h1>
          <p className="mt-3 font-literary text-[1.1rem] text-dim">
            a game of words and suspicion
          </p>
        </div>

        <div className="flex flex-col items-center gap-4">
          <button
            onClick={handlePlay}
            className="btn-action"
          >
            play &rarr;
          </button>
          <button
            onClick={handlePrivateGame}
            disabled={loading}
            className="font-system text-[0.75rem] text-dim transition-opacity hover:opacity-70 disabled:opacity-50"
          >
            {loading ? "creating..." : "private game"}
          </button>
        </div>

        <SystemText>
          play finds a game automatically &mdash; private game creates a link to
          share
        </SystemText>
      </div>
    </Stage>
  );
}
