import { create } from "zustand";

// --- Types matching backend SSE event models ---

export type GamePhase = "lobby" | "prompt" | "chat" | "vote" | "elimination" | "game_over";

export interface PlayerInfo {
  id: string;
  alias: string;
  is_alive: boolean;
  is_connected: boolean;
  is_host: boolean;
  eliminated_round: number | null;
  role?: string;
}

export interface ChatMsg {
  player_id: string;
  player_alias: string;
  text: string;
  is_answer?: boolean;
  timestamp?: string;
}

export interface RevealedPlayer {
  id: string;
  alias: string;
  role: string;
  is_alive: boolean;
  eliminated_round?: number;
}

interface StateSyncData {
  seq: number;
  phase: GamePhase;
  players: PlayerInfo[];
  round_number: number;
  prompt_text: string | null;
  prompt_category: string | null;
  answers: Record<string, string>;
  messages: ChatMsg[];
  my_answer: string | null;
  winner: string | null;
  is_host: boolean;
  phase_deadline: string | null;
}

interface PlayerEventData {
  seq: number;
  player_id: string;
  alias?: string;
  player_count?: number;
}

interface PhaseChangedData {
  seq: number;
  phase: GamePhase;
  round_number: number;
  prompt_text?: string;
  prompt_category?: string;
  phase_deadline?: string;
  answers?: Record<string, string>;
}

interface ChatMessageData {
  seq: number;
  player_id: string;
  player_alias: string;
  text: string;
  is_answer?: boolean;
}

interface CountData {
  seq: number;
  answer_count?: number;
  total_count?: number;
  vote_count?: number;
}

interface VoteResultsData {
  seq: number;
  votes: Record<string, string>;
  vote_tallies: Record<string, number>;
}

interface EliminationData {
  seq: number;
  eliminated_id: string | null;
  eliminated_alias: string | null;
  was_human: boolean | null;
  vote_count: number;
  tie: boolean;
  tie_message: string | null;
  no_votes: boolean;
}

interface GameOverData {
  seq: number;
  winner: string;
  players: RevealedPlayer[];
}

interface HostChangedData {
  seq: number;
  new_host_id: string;
}

interface SeqData {
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
  messages: ChatMsg[];
  myAnswer: string | null;
  myVote: string | null;
  answerCount: number;
  totalCount: number;
  voteCount: number;
  voteTotalCount: number;
  winner: string | null;
  lastSeq: number;

  // Timer
  phaseDeadline: string | null;

  // Elimination
  eliminatedId: string | null;
  eliminatedAlias: string | null;
  wasHuman: boolean | null;
  eliminationVoteCount: number;
  eliminationTie: boolean;
  eliminationTieMessage: string | null;
  eliminationNoVotes: boolean;

  // Vote results
  voteResults: Record<string, string> | null;
  voteTallies: Record<string, number> | null;

  // Game over
  revealedPlayers: RevealedPlayer[] | null;

  // Actions
  setIdentity: (gameId: string, playerId: string, alias: string) => void;
  onStateSync: (data: StateSyncData) => void;
  onPlayerJoined: (data: PlayerEventData) => void;
  onPlayerDisconnected: (data: PlayerEventData) => void;
  onPlayerReconnected: (data: PlayerEventData) => void;
  onPhaseChanged: (data: PhaseChangedData) => void;
  onChatMessage: (data: ChatMessageData) => void;
  onAnswerSubmitted: (data: CountData) => void;
  onVoteCast: (data: CountData) => void;
  onVoteResults: (data: VoteResultsData) => void;
  onElimination: (data: EliminationData) => void;
  onGameOver: (data: GameOverData) => void;
  onTimerTick: (data: SeqData) => void;
  onHostChanged: (data: HostChangedData) => void;
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
  messages: [] as ChatMsg[],
  myAnswer: null as string | null,
  myVote: null as string | null,
  answerCount: 0,
  totalCount: 0,
  voteCount: 0,
  voteTotalCount: 0,
  winner: null as string | null,
  lastSeq: 0,
  phaseDeadline: null as string | null,
  eliminatedId: null as string | null,
  eliminatedAlias: null as string | null,
  wasHuman: null as boolean | null,
  eliminationVoteCount: 0,
  eliminationTie: false,
  eliminationTieMessage: null as string | null,
  eliminationNoVotes: false,
  voteResults: null as Record<string, string> | null,
  voteTallies: null as Record<string, number> | null,
  revealedPlayers: null as RevealedPlayer[] | null,
};

export const useGameStore = create<GameState>((set, get) => ({
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
      messages: data.messages || [],
      myAnswer: data.my_answer,
      winner: data.winner,
      isHost: data.is_host,
      phaseDeadline: data.phase_deadline,
      lastSeq: data.seq,
      myVote: null,
      voteResults: null,
      voteTallies: null,
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
      answers: data.answers || {},
      lastSeq: data.seq,
      myAnswer: null,
      myVote: null,
      answerCount: 0,
      totalCount: 0,
      voteCount: 0,
      voteTotalCount: 0,
      messages: data.phase === "chat" ? [] : get().messages,
      eliminatedId: null,
      eliminatedAlias: null,
      wasHuman: null,
      eliminationVoteCount: 0,
      eliminationTie: false,
      eliminationTieMessage: null,
      eliminationNoVotes: false,
      voteResults: null,
      voteTallies: null,
    }),

  onChatMessage: (data) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          player_id: data.player_id,
          player_alias: data.player_alias,
          text: data.text,
          is_answer: data.is_answer,
        },
      ],
      lastSeq: data.seq,
    })),

  onAnswerSubmitted: (data) =>
    set({
      answerCount: data.answer_count || 0,
      totalCount: data.total_count || 0,
      lastSeq: data.seq,
    }),

  onVoteCast: (data) =>
    set({
      voteCount: data.vote_count || 0,
      voteTotalCount: data.total_count || 0,
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

  reset: () => set(initialState),
}));
