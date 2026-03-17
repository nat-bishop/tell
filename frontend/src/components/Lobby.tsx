"use client";

import { useState, useRef, useEffect } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { startGame } from "@/api/actions";
import { SystemText } from "./SystemText";

export function Lobby() {
  const { gameId, playerId, players, isHost } = useGameStore();
  const playerCount = players.filter((p) => p.is_alive).length;
  const canStart = playerCount >= 2;

  const [aiCount, setAiCount] = useState(2);
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    return () => clearTimeout(copyTimerRef.current);
  }, []);

  const handleStart = async () => {
    if (gameId && playerId) {
      await startGame(gameId, playerId, aiCount);
    }
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      clearTimeout(copyTimerRef.current);
      copyTimerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text for manual copy
    }
  };

  return (
    <div className="flex flex-col items-center gap-8 pt-16">
      <h1 className="font-literary text-[3rem] font-normal text-ink">
        tell
      </h1>

      <div className="flex flex-col items-center gap-3">
        {players.map((p) => (
          <div key={p.id} className="flex items-center gap-2 animate-fade-in">
            <span
              className={`font-literary-sc text-[1rem] tracking-[0.08em] ${p.is_connected ? 'text-ink' : 'text-dim'}`}
            >
              {p.alias}
            </span>
            {p.is_connected && (
              <span className="text-dim">&middot;</span>
            )}
          </div>
        ))}
      </div>

      <div className="synthesizing-dots font-system text-[0.75rem] text-dim">
        {playerCount} connected
      </div>

      {isHost && (
        <div className="flex flex-col items-center gap-4">
          {/* AI count selector */}
          <div className="flex items-center gap-3">
            <SystemText>ai players</SystemText>
            <div className="flex items-center gap-1">
              {[1, 2, 3].map((n) => (
                <button
                  key={n}
                  onClick={() => setAiCount(n)}
                  className={`font-system text-[0.8rem] w-8 h-8 transition-colors ${
                    aiCount === n
                      ? "text-ink border border-ink"
                      : "text-dim border border-rule"
                  }`}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!canStart}
            className="btn-action uppercase px-4"
          >
            begin
          </button>
        </div>
      )}

      {!isHost && <SystemText>waiting for host to begin</SystemText>}

      <button
        onClick={handleCopyLink}
        className="font-system text-[0.75rem] text-dim transition-opacity hover:text-ink"
      >
        {copied ? "copied" : "copy invite link"}
      </button>
    </div>
  );
}
