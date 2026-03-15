"use client";

import { useEffect, useRef } from "react";
import { connectGameEvents } from "@/api/events";
import { useGameStore } from "./useGameStore";

export function useGameEvents(gameId: string, playerId: string) {
  const connectionRef = useRef<{ close: () => void } | null>(null);
  const store = useGameStore();

  useEffect(() => {
    if (!gameId || !playerId) return;

    connectionRef.current = connectGameEvents(gameId, playerId, {
      onStateSync: store.onStateSync,
      onPlayerJoined: store.onPlayerJoined,
      onPlayerDisconnected: store.onPlayerDisconnected,
      onPlayerReconnected: store.onPlayerReconnected,
      onPhaseChanged: store.onPhaseChanged,
      onChatMessage: store.onChatMessage,
      onAnswerSubmitted: store.onAnswerSubmitted,
      onVoteCast: store.onVoteCast,
      onVoteResults: store.onVoteResults,
      onElimination: store.onElimination,
      onGameOver: store.onGameOver,
      onTimerTick: store.onTimerTick,
      onHostChanged: store.onHostChanged,
    });

    return () => {
      connectionRef.current?.close();
    };
    // Zustand actions are stable — only reconnect when IDs change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, playerId]);
}
