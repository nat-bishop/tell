"use client";

import { useEffect, useRef } from "react";
import { connectGameEvents } from "@/api/events";
import { useGameStore } from "./useGameStore";

export function useGameEvents(gameId: string, playerId: string) {
  const connectionRef = useRef<{ close: () => void } | null>(null);

  useEffect(() => {
    if (!gameId || !playerId) return;

    const store = useGameStore.getState();
    const lastSeq = store.lastSeq;

    connectionRef.current = connectGameEvents(gameId, playerId, {
      onStateSync: useGameStore.getState().onStateSync,
      onPlayerJoined: useGameStore.getState().onPlayerJoined,
      onPlayerDisconnected: useGameStore.getState().onPlayerDisconnected,
      onPlayerReconnected: useGameStore.getState().onPlayerReconnected,
      onPhaseChanged: useGameStore.getState().onPhaseChanged,
      onAnswerSubmitted: useGameStore.getState().onAnswerSubmitted,
      onVoteCast: useGameStore.getState().onVoteCast,
      onVoteResults: useGameStore.getState().onVoteResults,
      onElimination: useGameStore.getState().onElimination,
      onGameOver: useGameStore.getState().onGameOver,
      onTimerTick: useGameStore.getState().onTimerTick,
      onHostChanged: useGameStore.getState().onHostChanged,
      onNominationCast: useGameStore.getState().onNominationCast,
      onNominated: useGameStore.getState().onNominated,
      onQuestionSubmitted: useGameStore.getState().onQuestionSubmitted,
      onResponseSubmitted: useGameStore.getState().onResponseSubmitted,
      onSynthesisReady: useGameStore.getState().onSynthesisReady,
      onVerdict: useGameStore.getState().onVerdict,
    }, lastSeq);

    return () => {
      connectionRef.current?.close();
    };
  }, [gameId, playerId]);
}
