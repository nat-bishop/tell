import { BASE_URL } from "./client";

export interface GameEventCallbacks {
  onStateSync: (data: Record<string, unknown>) => void;
  onPlayerJoined: (data: Record<string, unknown>) => void;
  onPlayerDisconnected: (data: Record<string, unknown>) => void;
  onPlayerReconnected: (data: Record<string, unknown>) => void;
  onPhaseChanged: (data: Record<string, unknown>) => void;
  onChatMessage: (data: Record<string, unknown>) => void;
  onAnswerSubmitted: (data: Record<string, unknown>) => void;
  onVoteCast: (data: Record<string, unknown>) => void;
  onVoteResults: (data: Record<string, unknown>) => void;
  onElimination: (data: Record<string, unknown>) => void;
  onGameOver: (data: Record<string, unknown>) => void;
  onTimerTick: (data: Record<string, unknown>) => void;
  onHostChanged: (data: Record<string, unknown>) => void;
}

export function connectGameEvents(
  gameId: string,
  playerId: string,
  callbacks: GameEventCallbacks,
  lastSeq: number = 0,
): { close: () => void } {
  const url = `${BASE_URL}/games/${gameId}/events?player_id=${playerId}&last_seq=${lastSeq}`;
  const es = new EventSource(url);

  const eventMap: Record<string, (data: Record<string, unknown>) => void> = {
    state_sync: callbacks.onStateSync,
    player_joined: callbacks.onPlayerJoined,
    player_disconnected: callbacks.onPlayerDisconnected,
    player_reconnected: callbacks.onPlayerReconnected,
    phase_changed: callbacks.onPhaseChanged,
    chat_message: callbacks.onChatMessage,
    answer_submitted: callbacks.onAnswerSubmitted,
    vote_cast: callbacks.onVoteCast,
    vote_results: callbacks.onVoteResults,
    elimination: callbacks.onElimination,
    game_over: callbacks.onGameOver,
    timer_tick: callbacks.onTimerTick,
    host_changed: callbacks.onHostChanged,
  };

  for (const [eventType, handler] of Object.entries(eventMap)) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        handler(data);
      } catch {
        console.error(`Failed to parse ${eventType} event`, e.data);
      }
    });
  }

  es.onerror = () => {
    console.warn("SSE connection error, will auto-reconnect");
  };

  return { close: () => es.close() };
}
