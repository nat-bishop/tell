"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useGameStore, type PlayerInfo } from "@/hooks/useGameStore";
import { castVote } from "@/api/actions";
import { SystemText } from "./SystemText";

export function VoteOverlay() {
  const { gameId, playerId, players, voteCount, voteTotalCount } =
    useGameStore();
  const alivePlayers = players.filter(
    (p) => p.is_alive && p.id !== playerId,
  );
  const aliveCount = players.filter((p) => p.is_alive).length;
  const maxVotes = Math.min(3, Math.max(1, aliveCount - 1));

  const [selected, setSelected] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const sendVotes = useCallback(
    (targets: string[]) => {
      if (!gameId || !playerId) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        castVote(gameId, playerId, targets);
      }, 500);
    },
    [gameId, playerId],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const toggleVote = (pid: string) => {
    setSelected((prev) => {
      let next: string[];
      if (prev.includes(pid)) {
        next = prev.filter((id) => id !== pid);
      } else if (prev.length < maxVotes) {
        next = [...prev, pid];
      } else {
        return prev;
      }
      sendVotes(next);
      return next;
    });
  };

  // Sync to store for PlayerBar dots
  useEffect(() => {
    useGameStore.setState({ myVotes: selected });
  }, [selected]);

  return (
    <div className="border-t border-rule pt-4 mt-4">
      <span className="font-literary text-[1rem] text-ink">
        who is human?
      </span>
      <div className="flex flex-col gap-2 mt-3">
        {alivePlayers.map((p: PlayerInfo) => (
          <button
            key={p.id}
            onClick={() => toggleVote(p.id)}
            className="flex items-center py-2 pl-3 text-left transition-all min-h-[44px]"
            style={{
              borderLeft: selected.includes(p.id)
                ? "3px solid var(--warm)"
                : "3px solid transparent",
            }}
          >
            <span
              className={`font-literary-sc text-[0.95rem] tracking-[0.08em] ${
                selected.includes(p.id) ? "text-warm" : "text-ink"
              }`}
            >
              {p.alias}
            </span>
          </button>
        ))}
      </div>
      <div className="flex items-center justify-between mt-3">
        <SystemText>
          {selected.length} of {maxVotes} votes cast
        </SystemText>
        <SystemText>
          {voteCount} of {voteTotalCount} voted
        </SystemText>
      </div>
    </div>
  );
}
