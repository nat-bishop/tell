import { create } from "zustand";

// --- Types matching backend SSE event models ---

export type GamePhase =
  | "lobby"
  | "prompt"
  | "nominate"
  | "question"
  | "respond"
  | "review"
  | "elimination"
  | "game_over"
  | "chain";

export interface PlayerInfo {
  id: string;
  alias: string;
  is_alive: boolean;
  is_connected: boolean;
  is_host: boolean;
  eliminated_round: number | null;
  role?: string;
}

export interface QuestionEntryClient {
  target_id: string;
  target_alias: string;
  question: string;
  response: string | null;
  questioner_id?: string;
}

export interface RevealedPlayer {
  id: string;
  alias: string;
  role: string;
  is_alive: boolean;
  eliminated_round?: number;
}

export interface ChainRoundData {
  seed: string;
  responses: Record<string, string>;
  chosen_word: string | null;
  chosen_player_id: string | null;
}

export interface ChainSeedData {
  seq: number;
  word: string;
  round_index: number;
  sub_deadline: string | null;
  chain_so_far: string[];
  phase_duration: number | null;
}

export interface ChainProgressData {
  seq: number;
  round_index: number;
  count: number;
  total: number;
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
  questions: QuestionEntryClient[];
  assignments: Record<string, string>;
  nominated_id: string | null;
  nominations: Record<string, string>;
  synthesis: string | null;
  verdict: string | null;
  my_answer: string | null;
  my_votes: string[];
  winner: string | null;
  is_host: boolean;
  phase_deadline: string | null;
  phase_duration: number | null;
  writing_begins_at?: string | null;
  chain_rounds: ChainRoundData[];
  current_sub_round: number;
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
  assignments?: Record<string, string>;
  nominated_id?: string;
  questions?: QuestionEntryClient[];
  synthesis?: string;
  writing_begins_at?: string;
}

export interface CountData {
  seq: number;
  count: number;
  total: number;
}

export interface VoteResultsData {
  seq: number;
  votes: Record<string, string[]>;
  vote_tallies: Record<string, number>;
}

export interface EliminationData {
  seq: number;
  eliminated_id: string | null;
  eliminated_alias: string | null;
  was_human: boolean | null;
  vote_count: number;
  tie: boolean;
  tie_message: string | null;
  no_votes: boolean;
}

export interface GameOverData {
  seq: number;
  winner: string;
  players: RevealedPlayer[];
}

export interface HostChangedData {
  seq: number;
  new_host_id: string;
}

export interface NominatedData {
  seq: number;
  nominated_id: string;
  nominated_alias: string;
}

export interface SynthesisReadyData {
  seq: number;
  synthesis: string;
}

export interface VerdictData {
  seq: number;
  verdict: string;
}

export interface ResponseSubmittedData {
  seq: number;
  target_id: string;
  target_alias: string;
  response: string;
  count: number;
  total: number;
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
  questions: QuestionEntryClient[];
  assignments: Record<string, string>;
  nominatedId: string | null;
  synthesis: string | null;
  verdict: string | null;
  myQuestionSubmitted: boolean;
  myResponseSubmitted: boolean;
  questionCount: number;
  questionTotal: number;
  responseCount: number;
  responseTotal: number;
  nominationCount: number;
  nominationTotal: number;

  // Votes (multi-vote)
  myVotes: string[];
  voteCount: number;
  voteTotalCount: number;

  // Timer
  phaseDeadline: string | null;
  phaseDuration: number | null;

  // Reading period
  writingBeginsAt: string | null;

  // Word Chain
  chainRounds: ChainRoundData[];
  currentSubRound: number;
  currentSeedWord: string | null;
  chainSoFar: string[];
  chainResponseCount: number;
  chainTotalCount: number;

  // Elimination
  eliminatedId: string | null;
  eliminatedAlias: string | null;
  wasHuman: boolean | null;
  eliminationVoteCount: number;
  eliminationTie: boolean;
  eliminationTieMessage: string | null;
  eliminationNoVotes: boolean;

  // Vote results
  voteResults: Record<string, string[]> | null;
  voteTallies: Record<string, number> | null;

  // Game over
  revealedPlayers: RevealedPlayer[] | null;

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
  reset: () => void;
}

// Stable empty references to avoid unnecessary re-renders
const EMPTY_CHAIN_ROUNDS: ChainRoundData[] = [];
const EMPTY_CHAIN_SO_FAR: string[] = [];

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
  questions: [] as QuestionEntryClient[],
  assignments: {} as Record<string, string>,
  nominatedId: null as string | null,
  synthesis: null as string | null,
  verdict: null as string | null,
  myQuestionSubmitted: false,
  myResponseSubmitted: false,
  questionCount: 0,
  questionTotal: 0,
  responseCount: 0,
  responseTotal: 0,
  nominationCount: 0,
  nominationTotal: 0,
  myVotes: [] as string[],
  voteCount: 0,
  voteTotalCount: 0,
  phaseDeadline: null as string | null,
  phaseDuration: null as number | null,
  writingBeginsAt: null as string | null,
  chainRounds: [] as ChainRoundData[],
  currentSubRound: 0,
  currentSeedWord: null as string | null,
  chainSoFar: [] as string[],
  chainResponseCount: 0,
  chainTotalCount: 0,
  eliminatedId: null as string | null,
  eliminatedAlias: null as string | null,
  wasHuman: null as boolean | null,
  eliminationVoteCount: 0,
  eliminationTie: false,
  eliminationTieMessage: null as string | null,
  eliminationNoVotes: false,
  voteResults: null as Record<string, string[]> | null,
  voteTallies: null as Record<string, number> | null,
  revealedPlayers: null as RevealedPlayer[] | null,
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
      questions: data.questions || [],
      assignments: data.assignments || {},
      nominatedId: data.nominated_id,
      synthesis: data.synthesis,
      verdict: data.verdict,
      myAnswer: data.my_answer,
      winner: data.winner,
      isHost: data.is_host,
      phaseDeadline: data.phase_deadline,
      phaseDuration: data.phase_duration ?? null,
      writingBeginsAt: data.writing_begins_at ?? null,
      lastSeq: data.seq,
      connectionStatus: "connected",
      myVotes: data.my_votes || [],
      myQuestionSubmitted: false,
      myResponseSubmitted: false,
      voteResults: null,
      voteTallies: null,
      chainRounds: data.chain_rounds || [],
      currentSubRound: data.current_sub_round || 0,
      currentSeedWord:
        data.chain_rounds?.length > 0
          ? data.chain_rounds[data.chain_rounds.length - 1].seed
          : null,
      chainSoFar: data.chain_rounds?.map((cr: ChainRoundData) => cr.seed) || [],
    }),

  onPlayerJoined: (data) =>
    set((s) => ({
      players: [
        ...s.players.filter((p) => p.id !== data.player_id),
        {
          id: data.player_id,
          alias: data.alias || "???",
          is_alive: true,
          is_connected: true,
          is_host: false,
          eliminated_round: null,
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
    set({
      phase: data.phase,
      roundNumber: data.round_number,
      promptText: data.prompt_text || null,
      promptCategory: data.prompt_category || null,
      phaseDeadline: data.phase_deadline || null,
      phaseDuration: data.phase_duration ?? null,
      writingBeginsAt: data.writing_begins_at ?? null,
      answers: data.answers || {},
      roundType: data.round_type || null,
      assignments: data.assignments || {},
      nominatedId: data.nominated_id || null,
      questions: data.questions || [],
      synthesis: data.synthesis || null,
      lastSeq: data.seq,
      myAnswer: null,
      myVotes: [],
      myQuestionSubmitted: false,
      myResponseSubmitted: false,
      answerCount: 0,
      totalCount: 0,
      voteCount: 0,
      voteTotalCount: 0,
      questionCount: 0,
      questionTotal: 0,
      responseCount: 0,
      responseTotal: 0,
      nominationCount: 0,
      nominationTotal: 0,
      eliminatedId: null,
      eliminatedAlias: null,
      wasHuman: null,
      eliminationVoteCount: 0,
      eliminationTie: false,
      eliminationTieMessage: null,
      eliminationNoVotes: false,
      voteResults: null,
      voteTallies: null,
      verdict: null,
      chainRounds: EMPTY_CHAIN_ROUNDS,
      currentSubRound: 0,
      currentSeedWord: null,
      chainSoFar: EMPTY_CHAIN_SO_FAR,
      chainResponseCount: 0,
      chainTotalCount: 0,
    }),

  onAnswerSubmitted: (data) =>
    set({
      answerCount: data.count,
      totalCount: data.total,
      lastSeq: data.seq,
    }),

  onNominationCast: (data) =>
    set({
      nominationCount: data.count || 0,
      nominationTotal: data.total || 0,
      lastSeq: data.seq,
    }),

  onNominated: (data) =>
    set({
      nominatedId: data.nominated_id,
      lastSeq: data.seq,
    }),

  onQuestionSubmitted: (data) =>
    set({
      questionCount: data.count || 0,
      questionTotal: data.total || 0,
      lastSeq: data.seq,
    }),

  onResponseSubmitted: (data) =>
    set((s) => ({
      responseCount: data.count,
      responseTotal: data.total,
      lastSeq: data.seq,
      questions: s.questions.map((q) =>
        q.target_id === data.target_id ? { ...q, response: data.response } : q,
      ),
    })),

  onSynthesisReady: (data) =>
    set({
      synthesis: data.synthesis,
      lastSeq: data.seq,
    }),

  onVerdict: (data) =>
    set({
      verdict: data.verdict,
      lastSeq: data.seq,
    }),

  onChainSeed: (data) =>
    set({
      currentSeedWord: data.word,
      currentSubRound: data.round_index,
      chainSoFar: data.chain_so_far,
      phaseDeadline: data.sub_deadline,
      phaseDuration: data.phase_duration ?? 8,
      lastSeq: data.seq,
      chainResponseCount: 0,
      chainTotalCount: 0,
    }),

  onChainProgress: (data) =>
    set({
      chainResponseCount: data.count,
      chainTotalCount: data.total,
      lastSeq: data.seq,
    }),

  onVoteCast: (data) =>
    set({
      voteCount: data.count,
      voteTotalCount: data.total,
      lastSeq: data.seq,
    }),

  onVoteResults: (data) =>
    set({
      voteResults: data.votes,
      voteTallies: data.vote_tallies,
      lastSeq: data.seq,
    }),

  onElimination: (data) =>
    set((s) => ({
      eliminatedId: data.eliminated_id,
      eliminatedAlias: data.eliminated_alias,
      wasHuman: data.was_human,
      eliminationVoteCount: data.vote_count,
      eliminationTie: data.tie,
      eliminationTieMessage: data.tie_message,
      eliminationNoVotes: data.no_votes,
      lastSeq: data.seq,
      players: s.players.map((p) =>
        p.id === data.eliminated_id
          ? { ...p, is_alive: false, eliminated_round: s.roundNumber }
          : p,
      ),
    })),

  onGameOver: (data) =>
    set({
      phase: "game_over",
      winner: data.winner,
      revealedPlayers: data.players,
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

  onOpen: () => set({ connectionStatus: "connected" }),

  onError: () => set({ connectionStatus: "reconnecting" }),

  reset: () => set(initialState),
}));
