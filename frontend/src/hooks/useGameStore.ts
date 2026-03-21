import { create } from "zustand";

// --- Types matching backend SSE event models ---

export type GamePhase =
  | "lobby"
  | "round"
  | "game_over";

export interface PlayerInfo {
  id: string;
  alias: string;
  is_connected: boolean;
  is_host: boolean;
  score: number;
  role?: string;
}

export interface RevealedPlayer {
  id: string;
  alias: string;
  role: string;
  score: number;
}

export interface StateSyncData {
  seq: number;
  phase: GamePhase;
  players: PlayerInfo[];
  round_number: number;
  prompt_text: string | null;
  prompt_category: string | null;
  answers: Record<string, string>;
  round_type: string | null;
  my_answer: string | null;
  winner: string | null;
  winner_ids: string[];
  is_host: boolean;
  phase_deadline: string | null;
  phase_duration: number | null;
  scores: Record<string, number>;
  total_rounds: number;
  my_vote?: string | null;
  // Signal reconnection
  signal_phrase?: string | null;
  is_transmitter?: boolean;
  // Step fields
  step_name?: string | null;
  step_index?: number | null;
  component?: string | null;
  // Reconnection state
  sub_round_index?: number | null;
  sub_round_payload?: SubRoundPayload | null;
  round_results_payload?: RoundResultsPayload | null;
  round_scores?: Record<string, number> | null;
}

export interface PlayerEventData {
  seq: number;
  player_id: string;
  alias?: string;
  player_count?: number;
}

export interface StepChangedData {
  seq: number;
  phase: GamePhase;
  step_name: string;
  step_index: number;
  component: string;
  round_number: number;
  round_type: string;
  deadline: string | null;
  duration: number | null;
  payload: Record<string, unknown>;
}

export interface CountData {
  seq: number;
  count: number;
  total: number;
}

export interface GameOverData {
  seq: number;
  winner: string;
  winner_ids: string[];
  players: RevealedPlayer[];
  scores: Record<string, number>;
}

export interface HostChangedData {
  seq: number;
  new_host_id: string;
}

export interface NarrationData {
  seq: number;
  text: string;
  trigger: string;
}

// Generic sub-round payload (discriminated by round_type in the event)
export type SubRoundPayload =
  | {
      round_type: "brain_test";
      challenge_index: number;
      challenge_type: string;
      question: string;
      options: string[];
    }
  | {
      round_type: "wager";
      phase: "guess" | "bet";
      question_index: number;
      question: string;
      range_min: number;
      range_max: number;
      unit: string;
      total_questions: number;
      guesses?: Record<string, number>;
    }
  | {
      round_type: "signal";
      featured_player_id: string;
      featured_alias: string;
      transformation: string;
      constraint: string;
      total_transmitters?: number;
    };

// Generic round results payload (discriminated by round_type in the event)
export type RoundResultsPayload =
  | {
      round_type: "brain_test";
      results: Record<string, Array<{
        question: string;
        options: string[];
        selected_index: number;
        correct_index: number;
        challenge_type: string;
      }>>;
    }
  | {
      round_type: "task";
      vote_counts: Record<string, number>;
    }
  | {
      round_type: "wager";
      questions: Array<{
        question: string;
        correct_answer: number;
        range_min: number;
        range_max: number;
        unit: string;
        guesses: Record<string, number>;
        bets: Record<string, string>;
        closest_ids: string[];
      }>;
    }
  | {
      round_type: "signal";
      constraint: string;
      results: Record<string, {
        original_phrase: string;
        transformation: string;
        featured_alias: string;
        guesses: Record<string, string>;
        judgments: Record<string, number>;
        transmitter_score: number;
      }>;
    };

export interface RoundResultsData {
  seq: number;
  round_type: string;
  payload: Record<string, unknown>;
  scores: Record<string, number>;
}

export interface VoteSubmittedData {
  seq: number;
  player_id: string;
  vote_count: number;
  total: number;
}

export interface FinalRevealData {
  seq: number;
  players: RevealedPlayer[];
  winner_ids: string[];
}

export interface SeqData {
  seq: number;
}

// --- Store ---

interface GameState {
  // Identity
  gameId: string | null;
  playerId: string | null;
  myAlias: string | null;
  isHost: boolean;

  // Game state
  phase: GamePhase;
  players: PlayerInfo[];
  roundNumber: number;
  promptText: string | null;
  promptCategory: string | null;
  answers: Record<string, string>;
  myAnswer: string | null;
  answerCount: number;
  totalCount: number;
  winner: string | null;
  lastSeq: number;

  // Round-specific
  roundType: string | null;

  // Step-based state
  stepName: string | null;
  stepIndex: number;
  component: string | null;

  // Timer
  phaseDeadline: string | null;
  phaseDuration: number | null;

  // Scores
  scores: Record<string, number>;
  totalRounds: number;

  // Game over
  winnerIds: string[];
  revealedPlayers: RevealedPlayer[] | null;

  // Narration
  narrationText: string | null;
  narrationTrigger: string | null;
  narrationReceivedAt: number | null;

  // Generic round state
  subRoundIndex: number;
  subRoundPayload: SubRoundPayload | null;
  roundResults: RoundResultsPayload | null;
  roundScores: Record<string, number> | null;

  // Signal
  signalPhrase: string | null;
  isTransmitter: boolean;

  // Gallery vote
  votedForId: string | null;
  voteCount: number;

  // Connection
  connectionStatus: "connected" | "reconnecting" | "disconnected";

  // Actions
  setIdentity: (gameId: string, playerId: string, alias: string) => void;
  onStateSync: (data: StateSyncData) => void;
  onPlayerJoined: (data: PlayerEventData) => void;
  onPlayerDisconnected: (data: PlayerEventData) => void;
  onPlayerReconnected: (data: PlayerEventData) => void;
  onStepChanged: (data: StepChangedData) => void;
  onAnswerSubmitted: (data: CountData) => void;
  onGameOver: (data: GameOverData) => void;
  onTimerTick: (data: SeqData) => void;
  onHostChanged: (data: HostChangedData) => void;
  onNarration: (data: NarrationData) => void;
  onRoundResults: (data: RoundResultsData) => void;
  onVoteSubmitted: (data: VoteSubmittedData) => void;
  onFinalReveal: (data: FinalRevealData) => void;
  onOpen: () => void;
  onError: () => void;
  reset: () => void;
}

const initialState = {
  gameId: null as string | null,
  playerId: null as string | null,
  myAlias: null as string | null,
  isHost: false,
  phase: "lobby" as GamePhase,
  players: [] as PlayerInfo[],
  roundNumber: 0,
  promptText: null as string | null,
  promptCategory: null as string | null,
  answers: {} as Record<string, string>,
  myAnswer: null as string | null,
  answerCount: 0,
  totalCount: 0,
  winner: null as string | null,
  lastSeq: 0,
  roundType: null as string | null,
  stepName: null as string | null,
  stepIndex: 0,
  component: null as string | null,
  phaseDeadline: null as string | null,
  phaseDuration: null as number | null,
  scores: {} as Record<string, number>,
  totalRounds: 5,
  winnerIds: [] as string[],
  revealedPlayers: null as RevealedPlayer[] | null,
  narrationText: null as string | null,
  narrationTrigger: null as string | null,
  narrationReceivedAt: null as number | null,
  subRoundIndex: 0,
  subRoundPayload: null as SubRoundPayload | null,
  roundResults: null as RoundResultsPayload | null,
  roundScores: null as Record<string, number> | null,
  signalPhrase: null as string | null,
  isTransmitter: false,
  votedForId: null as string | null,
  voteCount: 0,
  connectionStatus: "connected" as "connected" | "reconnecting" | "disconnected",
};

export const useGameStore = create<GameState>((set) => ({
  ...initialState,

  setIdentity: (gameId, playerId, alias) =>
    set({ gameId, playerId, myAlias: alias }),

  onStateSync: (data) =>
    set({
      phase: data.phase,
      players: data.players,
      roundNumber: data.round_number,
      promptText: data.prompt_text,
      promptCategory: data.prompt_category,
      answers: data.answers || {},
      roundType: data.round_type,
      myAnswer: data.my_answer,
      winner: data.winner,
      winnerIds: data.winner_ids || [],
      isHost: data.is_host,
      phaseDeadline: data.phase_deadline,
      phaseDuration: data.phase_duration ?? null,
      scores: data.scores || {},
      totalRounds: data.total_rounds || 5,
      lastSeq: data.seq,
      signalPhrase: data.signal_phrase ?? null,
      isTransmitter: data.is_transmitter ?? false,
      votedForId: data.my_vote ?? null,
      stepName: data.step_name ?? null,
      stepIndex: data.step_index ?? 0,
      component: data.component ?? null,
      subRoundPayload: data.sub_round_payload ?? null,
      subRoundIndex: data.sub_round_index ?? 0,
      roundResults: data.round_results_payload
        ? ({ ...data.round_results_payload, round_type: data.round_type ?? "unknown" } as RoundResultsPayload)
        : null,
      roundScores: data.round_scores ?? null,
      connectionStatus: "connected",
    }),

  onPlayerJoined: (data) =>
    set((s) => ({
      players: [
        ...s.players.filter((p) => p.id !== data.player_id),
        {
          id: data.player_id,
          alias: data.alias || "???",
          is_connected: true,
          is_host: false,
          score: 0,
        },
      ],
      lastSeq: data.seq,
    })),

  onPlayerDisconnected: (data) =>
    set((s) => ({
      players: s.players.map((p) =>
        p.id === data.player_id ? { ...p, is_connected: false } : p,
      ),
      lastSeq: data.seq,
    })),

  onPlayerReconnected: (data) =>
    set((s) => ({
      players: s.players.map((p) =>
        p.id === data.player_id ? { ...p, is_connected: true } : p,
      ),
      lastSeq: data.seq,
    })),

  onStepChanged: (data) =>
    set((s) => {
      const isNewRound = data.round_number !== s.roundNumber;

      // Only clear narration if it has been visible for 4+ seconds
      const stale =
        s.narrationReceivedAt !== null && Date.now() - s.narrationReceivedAt > 4000;

      // Build sub-round payload from step payload for backwards compat
      let subRoundPayload: SubRoundPayload | null = null;
      const p = data.payload;
      if (p && typeof p === "object" && Object.keys(p).length > 0) {
        subRoundPayload = p as unknown as SubRoundPayload;
      }

      // Derive isTransmitter from transmitter_ids in signal_compose payload
      const transmitterIds = Array.isArray(p?.transmitter_ids) ? p.transmitter_ids as string[] : null;

      return {
        phase: data.phase,
        roundNumber: data.round_number,
        roundType: data.round_type || null,
        stepName: data.step_name,
        stepIndex: data.step_index,
        component: data.component,
        phaseDeadline: data.deadline || null,
        phaseDuration: data.duration ?? null,
        lastSeq: data.seq,
        // Payload-derived fields
        promptText: (p?.prompt_text as string) ?? s.promptText,
        promptCategory: (p?.prompt_category as string) ?? s.promptCategory,
        answers: (p?.answers as Record<string, string>) ?? (isNewRound ? {} : s.answers),
        subRoundPayload,
        subRoundIndex: (p?.sub_round_index as number) ?? data.step_index,
        isTransmitter: transmitterIds ? transmitterIds.includes(s.playerId ?? "") : s.isTransmitter,
        // Clear on new round
        ...(isNewRound ? {
          myAnswer: null,
          answerCount: 0,
          totalCount: 0,
          signalPhrase: null,
          isTransmitter: false,
          roundResults: null,
          roundScores: null,
          votedForId: null,
          voteCount: 0,
        } : {}),
        // Narration
        narrationText: stale ? null : s.narrationText,
        narrationTrigger: stale ? null : s.narrationTrigger,
        narrationReceivedAt: stale ? null : s.narrationReceivedAt,
      };
    }),

  onAnswerSubmitted: (data) =>
    set({
      answerCount: data.count,
      totalCount: data.total,
      lastSeq: data.seq,
    }),

  onNarration: (data) =>
    set({
      narrationText: data.text,
      narrationTrigger: data.trigger,
      narrationReceivedAt: Date.now(),
      lastSeq: data.seq,
    }),

  onRoundResults: (data) =>
    set((s) => ({
      roundResults: { round_type: data.round_type, ...data.payload } as RoundResultsPayload,
      roundScores: data.scores ?? null,
      scores: { ...s.scores, ...(data.scores || {}) },
      lastSeq: data.seq,
    })),

  onVoteSubmitted: (data) =>
    set({
      voteCount: data.vote_count,
      lastSeq: data.seq,
    }),

  onGameOver: (data) =>
    set({
      phase: "game_over",
      winner: data.winner,
      winnerIds: data.winner_ids || [],
      revealedPlayers: data.players,
      scores: data.scores || {},
      lastSeq: data.seq,
    }),

  onTimerTick: (data) => set({ lastSeq: data.seq }),

  onHostChanged: (data) =>
    set((s) => ({
      players: s.players.map((p) => ({
        ...p,
        is_host: p.id === data.new_host_id,
      })),
      isHost: s.playerId === data.new_host_id,
      lastSeq: data.seq,
    })),

  onFinalReveal: (data) =>
    set({
      revealedPlayers: data.players,
      winnerIds: data.winner_ids || [],
      lastSeq: data.seq,
    }),

  onOpen: () => set({ connectionStatus: "connected" }),

  onError: () => set({ connectionStatus: "reconnecting" }),

  reset: () => set(initialState),
}));
