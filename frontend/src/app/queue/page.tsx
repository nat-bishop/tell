"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { joinMatchmaking, leaveMatchmaking } from "@/api/actions";
import {
  connectMatchmakingEvents,
  type LobbyStatusData,
} from "@/api/matchmaking-events";
import { Stage } from "@/components/Stage";
import { SystemText } from "@/components/SystemText";

export default function QueuePage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [joined, setJoined] = useState(false);
  const [playerId, setPlayerId] = useState<string | null>(null);
  const [alias, setAlias] = useState<string | null>(null);
  const [status, setStatus] = useState<LobbyStatusData | null>(null);
  const [countdown, setCountdown] = useState<number | null>(null);
  const connectionRef = useRef<{ close: () => void } | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleJoin = async () => {
    if (!name.trim()) return;
    try {
      const res = await joinMatchmaking(name.trim());
      setPlayerId(res.player_id);
      setAlias(res.alias);
      setJoined(true);
    } catch (err) {
      console.error("Failed to join matchmaking", err);
    }
  };

  const handleLeave = useCallback(async () => {
    if (playerId) {
      connectionRef.current?.close();
      connectionRef.current = null;
      await leaveMatchmaking(playerId).catch(() => {});
    }
    setJoined(false);
    setPlayerId(null);
    setAlias(null);
    setStatus(null);
    setCountdown(null);
  }, [playerId]);

  // Connect SSE when joined
  useEffect(() => {
    if (!joined || !playerId) return;

    connectionRef.current = connectMatchmakingEvents(playerId, {
      onLobbyStatus: (data) => {
        setStatus(data);
        if (data.countdown_seconds !== null && data.countdown_seconds > 0) {
          setCountdown(data.countdown_seconds);
        }
      },
      onGameAssigned: (data) => {
        // Store identity for the game page
        sessionStorage.setItem(
          `tell-${data.game_id}`,
          JSON.stringify({ playerId, alias }),
        );
        router.push(`/game/${data.game_id}`);
      },
    });

    return () => {
      connectionRef.current?.close();
      connectionRef.current = null;
    };
  }, [joined, playerId, alias, router]);

  // Client-side countdown tick
  useEffect(() => {
    if (countdown === null || countdown <= 0) {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
      return;
    }

    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev === null || prev <= 1) return 0;
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    };
  }, [countdown !== null && countdown > 0]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Stage>
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-10">
        <div className="text-center">
          <h1 className="font-literary text-[3rem] font-normal text-ink">
            tell
          </h1>
          <p className="mt-3 font-literary text-[1.1rem] text-dim">
            finding a game
          </p>
        </div>

        {!joined ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleJoin();
            }}
            className="flex flex-col items-center gap-4"
          >
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="your name"
              maxLength={20}
              autoFocus
              className="w-48 border-b border-rule bg-transparent py-1 text-center font-literary text-[1.1rem] text-ink outline-none placeholder:text-dim focus:border-ink"
            />
            <button
              type="submit"
              disabled={!name.trim()}
              className="btn-action"
            >
              find game &rarr;
            </button>
          </form>
        ) : (
          <div className="flex flex-col items-center gap-6">
            {alias && (
              <div className="animate-fade-in text-center">
                <span className="font-literary-sc text-[1rem] tracking-[0.08em] text-ink">
                  {alias}
                </span>
              </div>
            )}

            <div className="flex flex-col items-center gap-2">
              {status && (
                <SystemText>{status.message}</SystemText>
              )}

              {countdown !== null && countdown > 0 && (
                <div className="font-system text-[0.85rem] text-ink animate-fade-in">
                  {countdown}
                </div>
              )}
            </div>

            <button
              onClick={handleLeave}
              className="font-system text-[0.7rem] text-dim transition-opacity hover:opacity-70"
            >
              leave queue
            </button>
          </div>
        )}
      </div>
    </Stage>
  );
}
