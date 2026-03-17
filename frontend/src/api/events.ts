import { API_URL } from "./client";
import type {
  StateSyncData,
  PlayerEventData,
  PhaseChangedData,
  CountData,
  VoteResultsData,
  EliminationData,
  GameOverData,
  SeqData,
  HostChangedData,
  NominatedData,
  ResponseSubmittedData,
  SynthesisReadyData,
  VerdictData,
  ChainSeedData,
  ChainProgressData,
} from "@/hooks/useGameStore";

export interface GameEventCallbacks {
  onStateSync: (data: StateSyncData) => void;
  onPlayerJoined: (data: PlayerEventData) => void;
  onPlayerDisconnected: (data: PlayerEventData) => void;
  onPlayerReconnected: (data: PlayerEventData) => void;
  onPhaseChanged: (data: PhaseChangedData) => void;
  onAnswerSubmitted: (data: CountData) => void;
  onVoteCast: (data: CountData) => void;
  onVoteResults: (data: VoteResultsData) => void;
  onElimination: (data: EliminationData) => void;
  onGameOver: (data: GameOverData) => void;
  onTimerTick: (data: SeqData) => void;
  onHostChanged: (data: HostChangedData) => void;
  onNominationCast: (data: CountData) => void;
  onNominated: (data: NominatedData) => void;
  onQuestionSubmitted: (data: CountData) => void;
  onResponseSubmitted: (data: ResponseSubmittedData) => void;
  onSynthesisReady: (data: SynthesisReadyData) => void;
  onVerdict: (data: VerdictData) => void;
  onChainSeed: (data: ChainSeedData) => void;
  onChainProgress: (data: ChainProgressData) => void;
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

  es.onopen = () => {
    callbacks.onOpen();
  };

  es.onerror = () => {
    console.warn("SSE connection error, will auto-reconnect");
    callbacks.onError();
  };

  return { close: () => es.close() };
}
