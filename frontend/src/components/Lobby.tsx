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
      <h1
        className="font-system text-[2.5rem] font-normal text-ink tracking-[0.15em] uppercase animate-glitch"
        style={{ textShadow: '0 0 40px var(--cold-glow)' }}
      >
        tell
      </h1>

      <div className="flex flex-col items-center gap-3">
        {players.map((p) => (
          <div key={p.id} className="flex items-center gap-2 animate-fade-in">
            <span
              className={`inline-block w-2 h-2 rounded-full ${p.is_connected ? 'bg-cold' : 'bg-rule'}`}
              style={p.is_connected ? { boxShadow: '0 0 6px var(--cold)' } : undefined}
            />
            <span
              className={`font-system text-[0.85rem] tracking-[0.1em] uppercase ${p.is_connected ? 'text-ink' : 'text-dim'}`}
            >
              {p.alias}
            </span>
          </div>
        ))}
      </div>

      <div className="synthesizing-dots font-system text-[0.75rem] text-cold tracking-wide">
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
                  className={`font-system text-[0.8rem] w-8 h-8 rounded transition-all duration-200 ${
                    aiCount === n
                      ? "text-ink border border-cold bg-raised"
                      : "text-dim border border-rule"
                  }`}
                  style={aiCount === n ? { boxShadow: '0 0 8px var(--cold-glow)' } : undefined}
                >
                  {n}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleStart}
            disabled={!canStart}
            className="btn-action"
          >
            begin
          </button>
        </div>
      )}

      {!isHost && <SystemText>waiting for host to begin</SystemText>}

      <button
        onClick={handleCopyLink}
        className="font-system text-[0.75rem] text-dim tracking-wide transition-all hover:text-cold"
      >
        {copied ? "copied" : "copy invite link"}
      </button>
    </div>
  );
}
