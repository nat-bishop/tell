import { SSE_URL } from "./client";

// Callbacks accept parsed JSON — type safety is enforced by the store, not the transport layer
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type EventHandler = (data: any) => void;

export interface GameEventCallbacks {
  onStateSync: EventHandler;
  onPlayerJoined: EventHandler;
  onPlayerDisconnected: EventHandler;
  onPlayerReconnected: EventHandler;
  onPhaseChanged: EventHandler;
  onAnswerSubmitted: EventHandler;
  onVoteCast: EventHandler;
  onVoteResults: EventHandler;
  onElimination: EventHandler;
  onGameOver: EventHandler;
  onTimerTick: EventHandler;
  onHostChanged: EventHandler;
  onNominationCast: EventHandler;
  onNominated: EventHandler;
  onQuestionSubmitted: EventHandler;
  onResponseSubmitted: EventHandler;
  onSynthesisReady: EventHandler;
  onVerdict: EventHandler;
  onChainSeed: EventHandler;
  onChainProgress: EventHandler;
}

export function connectGameEvents(
  gameId: string,
  playerId: string,
  callbacks: GameEventCallbacks,
  lastSeq: number = 0,
): { close: () => void } {
  const url = `${SSE_URL}/games/${gameId}/events?player_id=${playerId}&last_seq=${lastSeq}`;
  const es = new EventSource(url);

  const eventMap: Record<string, EventHandler> = {
    state_sync: callbacks.onStateSync,
    player_joined: callbacks.onPlayerJoined,
    player_disconnected: callbacks.onPlayerDisconnected,
    player_reconnected: callbacks.onPlayerReconnected,
    phase_changed: callbacks.onPhaseChanged,
    answer_submitted: callbacks.onAnswerSubmitted,
    vote_cast: callbacks.onVoteCast,
    vote_results: callbacks.onVoteResults,
    elimination: callbacks.onElimination,
    game_over: callbacks.onGameOver,
    timer_tick: callbacks.onTimerTick,
    host_changed: callbacks.onHostChanged,
    nomination_cast: callbacks.onNominationCast,
    nominated: callbacks.onNominated,
    question_submitted: callbacks.onQuestionSubmitted,
    response_submitted: callbacks.onResponseSubmitted,
    synthesis_ready: callbacks.onSynthesisReady,
    verdict: callbacks.onVerdict,
    chain_seed: callbacks.onChainSeed,
    chain_progress: callbacks.onChainProgress,
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
