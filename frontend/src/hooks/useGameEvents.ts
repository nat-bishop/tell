"use client";

import { useEffect, useRef } from "react";
import { connectGameEvents } from "@/api/events";
import { useGameStore } from "./useGameStore";

export function useGameEvents(gameId: string, playerId: string) {
  const connectionRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    if (!gameId || !playerId) return;

    // Use getState() to avoid subscribing to the entire store
    const store = useGameStore.getState();
    const lastSeq = store.lastSeq;

    connectionRef.current = connectGameEvents(gameId, playerId, {
      onStateSync: useGameStore.getState().onStateSync,
      onPlayerJoined: useGameStore.getState().onPlayerJoined,
      onPlayerDisconnected: useGameStore.getState().onPlayerDisconnected,
      onPlayerReconnected: useGameStore.getState().onPlayerReconnected,
      onPhaseChanged: useGameStore.getState().onPhaseChanged,
      onChatMessage: useGameStore.getState().onChatMessage,
      onAnswerSubmitted: useGameStore.getState().onAnswerSubmitted,
      onVoteCast: useGameStore.getState().onVoteCast,
      onVoteResults: useGameStore.getState().onVoteResults,
      onElimination: useGameStore.getState().onElimination,
      onGameOver: useGameStore.getState().onGameOver,
      onTimerTick: useGameStore.getState().onTimerTick,
      onHostChanged: useGameStore.getState().onHostChanged,
    }, lastSeq);

    return () => {
      connectionRef.current?.close();
    };
  }, [gameId, playerId]);
}
