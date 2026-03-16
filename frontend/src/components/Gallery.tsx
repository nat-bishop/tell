"use client";

import type { PlayerInfo } from "@/hooks/useGameStore";

interface GalleryProps {
  players: PlayerInfo[];
  renderCard: (player: PlayerInfo) => React.ReactNode;
}

export function Gallery({ players, renderCard }: GalleryProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {players.map((p) => (
        <div key={p.id} className="animate-fade-in">
          {renderCard(p)}
        </div>
      ))}
    </div>
  );
}
