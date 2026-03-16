"use client";

import { useState, useEffect, useCallback } from "react";
import type { PlayerInfo } from "@/hooks/useGameStore";

interface SpotlightProps {
  players: PlayerInfo[];
  renderContent: (player: PlayerInfo) => React.ReactNode;
  secondsPerPlayer: number;
}

export function Spotlight({
  players,
  renderContent,
  secondsPerPlayer,
}: SpotlightProps) {
  const [index, setIndex] = useState(0);

  const advance = useCallback(() => {
    setIndex((i) => (i + 1) % players.length);
  }, [players.length]);

  useEffect(() => {
    if (players.length <= 1) return;
    const interval = setInterval(advance, secondsPerPlayer * 1000);
    return () => clearInterval(interval);
  }, [advance, secondsPerPlayer, players.length]);

  if (players.length === 0) return null;

  const current = players[index];

  return (
    <div className="flex flex-col items-center gap-4">
      <div key={current.id} className="w-full max-w-md animate-fade-in">
        {renderContent(current)}
      </div>
      {players.length > 1 && (
        <div className="flex gap-1.5">
          {players.map((_, i) => (
            <span
              key={i}
              className={`inline-block w-1.5 h-1.5 rounded-full transition-colors ${
                i === index ? "bg-ink" : "bg-rule"
              }`}
            />
          ))}
        </div>
      )}
    </div>
  );
}
