"use client";

import { useEffect, useState, use } from "react";
import { Stage } from "@/components/Stage";
import { SystemText } from "@/components/SystemText";
import { joinGame, createGame } from "@/api/actions";
import { useGameStore } from "@/hooks/useGameStore";
import { useGameEvents } from "@/hooks/useGameEvents";
import { useRouter } from "next/navigation";
import { FacilityGameContent } from "@/facility/FacilityGameContent";

function JoinScreen({
  gameId,
  onJoined,
}: {
  gameId: string;
  onJoined: (playerId: string, alias: string) => void;
}) {
  const [name, setName] = useState("");
  const [joining, setJoining] = useState(false);

  const handleJoin = async () => {
    if (!name.trim()) return;
    setJoining(true);
    try {
      const res = await joinGame(gameId, name.trim());
      onJoined(res.player_id, res.alias);
    } catch {
      setJoining(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleJoin();
  };

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-8">
      <h1 className="font-literary text-[3rem] font-normal text-ink">
        tell
      </h1>
      <div className="w-full max-w-xs">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full border-b bg-transparent py-2 min-h-[44px] text-center font-literary text-[1.1rem] text-ink outline-none border-rule"
          placeholder="your name"
          autoFocus
        />
      </div>
      <button
        onClick={handleJoin}
        disabled={joining || !name.trim()}
        className="btn-action px-4"
      >
        {joining ? "joining..." : "enter \u2192"}
      </button>
    </div>
  );
}

export default function GamePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { setIdentity, playerId } = useGameStore();
  const [joined, setJoined] = useState(false);

  useEffect(() => {
    if (id === "new") {
      createGame().then((res) => router.replace(`/game/${res.game_id}`));
    }
  }, [id, router]);

  useEffect(() => {
    if (id === "new") return;
    const stored = sessionStorage.getItem(`tell-${id}`);
    if (stored) {
      try {
        const { playerId: pid, alias } = JSON.parse(stored);
        setIdentity(id, pid, alias);
        setJoined(true);
        return;
      } catch {
        sessionStorage.removeItem(`tell-${id}`);
      }
    }
    setJoined(false);
  }, [id, setIdentity]);

  useGameEvents(joined ? id : "", joined ? playerId || "" : "");

  if (id === "new") {
    return (
      <Stage>
        <div className="flex min-h-[60vh] items-center justify-center">
          <SystemText>creating game...</SystemText>
        </div>
      </Stage>
    );
  }

  if (!joined) {
    return (
      <Stage>
        <JoinScreen
          gameId={id}
          onJoined={(pid, alias) => {
            sessionStorage.setItem(
              `tell-${id}`,
              JSON.stringify({ playerId: pid, alias }),
            );
            setIdentity(id, pid, alias);
            setJoined(true);
          }}
        />
      </Stage>
    );
  }

  return <FacilityGameContent />;
}
