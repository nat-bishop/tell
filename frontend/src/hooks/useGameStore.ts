import { create } from "zustand";

// --- Types matching backend SSE event models ---

export type GamePhase =
  | "lobby"
  | "prompt"
  | "active"
  | "results"
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
  action_starts_at?: string | null;
  scores: Record<string, number>;
  total_rounds: number;
  my_vote?: string | null;
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

export interface PhaseChangedData {
  seq: number;
  phase: GamePhase;
  round_number: number;
  prompt_text?: string;
  prompt_category?: string;
  phase_deadline?: string;
  phase_duration?: number;
  answers?: Record<string, string>;
  round_type?: string;
  action_starts_at?: string;
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
    };

export interface SubRoundData {
  seq: number;
  round_type: string;
  sub_round_index: number;
  payload: SubRoundPayload;
  sub_deadline: string | null;
  phase_duration: number | null;
}

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
  narrator_text: string | null;
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

  // Timer
  phaseDeadline: string | null;
  phaseDuration: number | null;

  // Interstitial
  actionStartsAt: string | null;

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
  onPhaseChanged: (data: PhaseChangedData) => void;
  onAnswerSubmitted: (data: CountData) => void;
  onGameOver: (data: GameOverData) => void;
  onTimerTick: (data: SeqData) => void;
  onHostChanged: (data: HostChangedData) => void;
  onNarration: (data: NarrationData) => void;
  onSubRound: (data: SubRoundData) => void;
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
  phaseDeadline: null as string | null,
  phaseDuration: null as number | null,
  actionStartsAt: null as string | null,
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
      actionStartsAt: data.action_starts_at ?? null,
      scores: data.scores || {},
      totalRounds: data.total_rounds || 5,
      lastSeq: data.seq,
      votedForId: data.my_vote ?? null,
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

  onPhaseChanged: (data) =>
    set((s) => {
      // Only clear narration if it has been visible for 4+ seconds
      const stale =
        s.narrationReceivedAt !== null && Date.now() - s.narrationReceivedAt > 4000;
      return {
        phase: data.phase,
        roundNumber: data.round_number,
        promptText: data.prompt_text || null,
        promptCategory: data.prompt_category || null,
        phaseDeadline: data.phase_deadline || null,
        phaseDuration: data.phase_duration ?? null,
        actionStartsAt: data.action_starts_at ?? null,
        answers: data.answers || {},
        roundType: data.round_type || null,
        lastSeq: data.seq,
        myAnswer: null,
        answerCount: 0,
        totalCount: data.phase === "prompt" ? s.players.length : 0,
        narrationText: stale ? null : s.narrationText,
        narrationTrigger: stale ? null : s.narrationTrigger,
        narrationReceivedAt: stale ? null : s.narrationReceivedAt,
        // Generic round state reset
        subRoundPayload: null,
        subRoundIndex: 0,
        roundResults: null,
        roundScores: null,
        votedForId: null,
        voteCount: 0,
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

  onSubRound: (data) =>
    set({
      subRoundPayload: data.payload,
      subRoundIndex: data.sub_round_index,
      phaseDeadline: data.sub_deadline,
      phaseDuration: data.phase_duration ?? 12,
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
      narrationText: data.narrator_text,
      narrationTrigger: "game_over",
      narrationReceivedAt: Date.now(),
      lastSeq: data.seq,
    }),

  onOpen: () => set({ connectionStatus: "connected" }),

  onError: () => set({ connectionStatus: "reconnecting" }),

  reset: () => set(initialState),
}));
