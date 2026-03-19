import { log } from "@/lib/log";
import { API_URL } from "./client";
import type {
  StateSyncData,
  PlayerEventData,
  PhaseChangedData,
  CountData,
  GameOverData,
  SeqData,
  HostChangedData,
  NarrationData,
  SubRoundData,
  RoundResultsData,
  FinalRevealData,
} from "@/hooks/useGameStore";

export interface GameEventCallbacks {
  onStateSync: (data: StateSyncData) => void;
  onPlayerJoined: (data: PlayerEventData) => void;
  onPlayerDisconnected: (data: PlayerEventData) => void;
  onPlayerReconnected: (data: PlayerEventData) => void;
  onPhaseChanged: (data: PhaseChangedData) => void;
  onAnswerSubmitted: (data: CountData) => void;
  onGameOver: (data: GameOverData) => void;
  onTimerTick: (data: SeqData) => void;
  onHostChanged: (data: HostChangedData) => void;
  onNarration: (data: NarrationData) => void;
  onSubRound: (data: SubRoundData) => void;
  onRoundResults: (data: RoundResultsData) => void;
  onFinalReveal: (data: FinalRevealData) => void;
  onOpen: () => void;
  onError: () => void;
}

export function connectGameEvents(
  gameId: string,
  playerId: string,
  callbacks: GameEventCallbacks,
  lastSeq: number = 0,
): { close: () => void } {
  const url = `${API_URL}/games/${gameId}/events?player_id=${playerId}&last_seq=${lastSeq}`;
  const es = new EventSource(url);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const eventMap: Record<string, (data: any) => void> = {
    state_sync: callbacks.onStateSync,
    player_joined: callbacks.onPlayerJoined,
    player_disconnected: callbacks.onPlayerDisconnected,
    player_reconnected: callbacks.onPlayerReconnected,
    phase_changed: callbacks.onPhaseChanged,
    answer_submitted: callbacks.onAnswerSubmitted,
    game_over: callbacks.onGameOver,
    timer_tick: callbacks.onTimerTick,
    host_changed: callbacks.onHostChanged,
    narration: callbacks.onNarration,
    sub_round: callbacks.onSubRound,
    round_results: callbacks.onRoundResults,
    final_reveal: callbacks.onFinalReveal,
  };

  for (const [eventType, handler] of Object.entries(eventMap)) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        log.debug("sse_event", { event_type: eventType, seq: data.seq });
        handler(data);
      } catch {
        log.error("sse_parse_failed", { event_type: eventType });
      }
    });
  }

  es.onopen = () => {
    callbacks.onOpen();
  };

  es.onerror = () => {
    log.warn("sse_connection_error");
    callbacks.onError();
  };

  return { close: () => es.close() };
}
