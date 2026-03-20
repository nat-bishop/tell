"use client";

import { useEffect, useRef } from "react";
import { connectGameEvents } from "@/api/events";
import { useGameStore } from "./useGameStore";

export function useGameEvents(gameId: string, playerId: string) {
  const connectionRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    if (!gameId || !playerId) return;

    connectionRef.current = connectGameEvents(gameId, playerId, {
      onStateSync: useGameStore.getState().onStateSync,
      onPlayerJoined: useGameStore.getState().onPlayerJoined,
      onPlayerDisconnected: useGameStore.getState().onPlayerDisconnected,
      onPlayerReconnected: useGameStore.getState().onPlayerReconnected,
      onPhaseChanged: useGameStore.getState().onPhaseChanged,
      onAnswerSubmitted: useGameStore.getState().onAnswerSubmitted,
      onGameOver: useGameStore.getState().onGameOver,
      onTimerTick: useGameStore.getState().onTimerTick,
      onHostChanged: useGameStore.getState().onHostChanged,
      onNarration: useGameStore.getState().onNarration,
      onSubRound: useGameStore.getState().onSubRound,
      onRoundResults: useGameStore.getState().onRoundResults,
      onVoteSubmitted: useGameStore.getState().onVoteSubmitted,
      onFinalReveal: useGameStore.getState().onFinalReveal,
      onOpen: useGameStore.getState().onOpen,
      onError: useGameStore.getState().onError,
    }, () => useGameStore.getState().lastSeq);

    return () => {
      connectionRef.current?.close();
    };
  }, [gameId, playerId]);
}
