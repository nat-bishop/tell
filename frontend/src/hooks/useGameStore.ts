import { create } from "zustand";

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

/* eslint-disable @typescript-eslint/no-explicit-any */
interface GameState {
  // Identity
  gameId: string | null;
  playerId: string | null;
  myAlias: string | null;
  isHost: boolean;

  // Game state
  phase: string;
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
  revealedPlayers: any[] | null;

  // Actions
  setIdentity: (gameId: string, playerId: string, alias: string) => void;
  onStateSync: (data: any) => void;
  onPlayerJoined: (data: any) => void;
  onPlayerDisconnected: (data: any) => void;
  onPlayerReconnected: (data: any) => void;
  onPhaseChanged: (data: any) => void;
  onChatMessage: (data: any) => void;
  onAnswerSubmitted: (data: any) => void;
  onVoteCast: (data: any) => void;
  onVoteResults: (data: any) => void;
  onElimination: (data: any) => void;
  onGameOver: (data: any) => void;
  onTimerTick: (data: any) => void;
  onHostChanged: (data: any) => void;
  reset: () => void;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

const initialState = {
  gameId: null as string | null,
  playerId: null as string | null,
  myAlias: null as string | null,
  isHost: false,
  phase: "lobby",
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
  revealedPlayers: null as any[] | null, // eslint-disable-line @typescript-eslint/no-explicit-any
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
          alias: data.alias,
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
      answerCount: data.answer_count,
      totalCount: data.total_count,
      lastSeq: data.seq,
    }),

  onVoteCast: (data) =>
    set({
      voteCount: data.vote_count,
      voteTotalCount: data.total_count,
      lastSeq: data.seq,
    }),

  onVoteResults: (data) =>
    set({
      voteResults: data.votes,
      voteTallies: data.vote_tallies,
      lastSeq: data.seq,
    }),

  onElimination: (data) =>
    set({
      eliminatedId: data.eliminated_id,
      eliminatedAlias: data.eliminated_alias,
      wasHuman: data.was_human,
      eliminationVoteCount: data.vote_count,
      eliminationTie: data.tie,
      eliminationTieMessage: data.tie_message,
      eliminationNoVotes: data.no_votes,
      lastSeq: data.seq,
      players: get().players.map((p) =>
        p.id === data.eliminated_id
          ? { ...p, is_alive: false, eliminated_round: get().roundNumber }
          : p,
      ),
    }),

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
