import { create } from "zustand";
import { log } from "@/lib/log";

// --- Types matching backend SSE event models ---

export type GamePhase =
  | "lobby"
  | "prompt"
  | "game_over"
  | "brain_test"
  | "brain_test_results"
  | "matchup";

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
  writing_begins_at?: string | null;
  action_starts_at?: string | null;
  scores: Record<string, number>;
  total_rounds: number;
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
  writing_begins_at?: string;
  action_starts_at?: string;
  matchups?: MatchupInfo[];
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

export interface BrainTestChallengeData {
  seq: number;
  challenge_index: number;
  challenge_type: string;
  question: string;
  options: string[];
  sub_deadline: string | null;
  phase_duration: number | null;
}

export interface BrainTestResultsData {
  seq: number;
  results: Record<string, Array<{
    question: string;
    options: string[];
    selected_index: number;
    correct_index: number;
    challenge_type: string;
  }>>;
  scores: Record<string, number>;
}

export interface MatchupChallengeData {
  seq: number;
  matchup_index: number;
  left_player_id: string;
  left_alias: string;
  left_answer: string;
  right_player_id: string;
  right_alias: string;
  right_answer: string;
  prompt_text: string;
  sub_deadline: string | null;
  phase_duration: number | null;
}

export interface MatchupResultsData {
  seq: number;
  matchup_results: Array<{
    matchup_index: number;
    left_player_id: string;
    left_alias: string;
    left_votes: number;
    right_player_id: string;
    right_alias: string;
    right_votes: number;
    prompt_text: string;
  }>;
  scores: Record<string, number>;
}

export interface FinalRevealData {
  seq: number;
  players: RevealedPlayer[];
  winner_ids: string[];
  narrator_text: string | null;
}

export interface MatchupInfo {
  pair: string[];
  prompt_text: string;
  prompt_category: string;
  left_alias: string;
  right_alias: string;
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

  // Reading period
  writingBeginsAt: string | null;

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

  // Brain Test
  brainTestQuestion: string | null;
  brainTestChallengeIndex: number;
  brainTestChallengeType: string | null;
  brainTestOptions: string[];
  brainTestResults: Record<string, Array<{
    question: string; options: string[]; selected_index: number; correct_index: number; challenge_type: string;
  }>> | null;

  // Brain Test scores
  brainTestScores: Record<string, number> | null;

  // Matchup
  matchups: MatchupInfo[] | null;
  myMatchupPrompt: string | null;
  byePlayerId: string | null;
  matchupIndex: number;
  matchupLeftId: string | null;
  matchupLeftAlias: string | null;
  matchupLeftAnswer: string | null;
  matchupRightId: string | null;
  matchupRightAlias: string | null;
  matchupRightAnswer: string | null;
  matchupPromptText: string | null;
  matchupMyVote: number | null;  // 0=left, 1=right
  matchupResults: MatchupResultsData | null;

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
  onBrainTestChallenge: (data: BrainTestChallengeData) => void;
  onBrainTestResults: (data: BrainTestResultsData) => void;
  onMatchupChallenge: (data: MatchupChallengeData) => void;
  onMatchupResults: (data: MatchupResultsData) => void;
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
  writingBeginsAt: null as string | null,
  actionStartsAt: null as string | null,
  scores: {} as Record<string, number>,
  totalRounds: 5,
  winnerIds: [] as string[],
  revealedPlayers: null as RevealedPlayer[] | null,
  narrationText: null as string | null,
  narrationTrigger: null as string | null,
  brainTestQuestion: null as string | null,
  brainTestChallengeIndex: 0,
  brainTestChallengeType: null as string | null,
  brainTestOptions: [] as string[],
  brainTestResults: null as Record<string, Array<{
    question: string; options: string[]; selected_index: number; correct_index: number; challenge_type: string;
  }>> | null,
  brainTestScores: null as Record<string, number> | null,
  matchups: null as MatchupInfo[] | null,
  myMatchupPrompt: null as string | null,
  byePlayerId: null as string | null,
  matchupIndex: 0,
  matchupLeftId: null as string | null,
  matchupLeftAlias: null as string | null,
  matchupLeftAnswer: null as string | null,
  matchupRightId: null as string | null,
  matchupRightAlias: null as string | null,
  matchupRightAnswer: null as string | null,
  matchupPromptText: null as string | null,
  matchupMyVote: null as number | null,
  matchupResults: null as MatchupResultsData | null,
  connectionStatus: "connected" as "connected" | "reconnecting" | "disconnected",
};

export const useGameStore = create<GameState>((set) => ({
  ...initialState,

  setIdentity: (gameId, playerId, alias) =>
    set({ gameId, playerId, myAlias: alias }),

  onStateSync: (data) => {
    log.info("state_sync", { phase: data.phase, round: data.round_number, player_count: data.players.length });
    return set({
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
      writingBeginsAt: data.writing_begins_at ?? null,
      actionStartsAt: data.action_starts_at ?? null,
      scores: data.scores || {},
      totalRounds: data.total_rounds || 5,
      lastSeq: data.seq,
      connectionStatus: "connected",
    });
  },

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

  onPhaseChanged: (data) => {
    log.info("phase_changed", { phase: data.phase, round: data.round_number, round_type: data.round_type });
    return set((s) => ({
      phase: data.phase,
      roundNumber: data.round_number,
      promptText: data.prompt_text || null,
      promptCategory: data.prompt_category || null,
      phaseDeadline: data.phase_deadline || null,
      phaseDuration: data.phase_duration ?? null,
      writingBeginsAt: data.writing_begins_at ?? null,
      actionStartsAt: data.action_starts_at ?? null,
      answers: data.answers || {},
      roundType: data.round_type || null,
      lastSeq: data.seq,
      myAnswer: null,
      answerCount: 0,
      totalCount: data.phase === "prompt"
        ? (() => {
            const total = s.players.length;
            // Subtract bye player for matchup rounds
            if (data.matchups) {
              const paired = new Set(data.matchups.flatMap(m => m.pair));
              const byeCount = s.players.filter(p => !paired.has(p.id)).length;
              return total - byeCount;
            }
            return total;
          })()
        : 0,
      narrationText: null,
      narrationTrigger: null,
      // Brain test reset
      brainTestQuestion: null,
      brainTestChallengeIndex: 0,
      brainTestChallengeType: null,
      brainTestOptions: [],
      brainTestResults: null,
      brainTestScores: null,
      // Matchup data — preserve existing if not provided (MATCHUP phase reuses PROMPT data)
      matchups: data.matchups ?? s.matchups,
      myMatchupPrompt: (() => {
        const matchupList = data.matchups || s.matchups;
        if (!matchupList || !s.playerId) return null;
        for (const mu of matchupList) {
          if (mu.pair.includes(s.playerId)) return mu.prompt_text;
        }
        return null; // bye player
      })(),
      byePlayerId: (() => {
        const matchupList = data.matchups || s.matchups;
        if (!matchupList || !s.playerId) return null;
        const allPaired = new Set(matchupList.flatMap(mu => mu.pair));
        for (const p of s.players) {
          if (!allPaired.has(p.id)) return p.id;
        }
        return null;
      })(),
      matchupIndex: 0,
      matchupLeftId: null,
      matchupLeftAlias: null,
      matchupLeftAnswer: null,
      matchupRightId: null,
      matchupRightAlias: null,
      matchupRightAnswer: null,
      matchupPromptText: null,
      matchupMyVote: null,
      matchupResults: null,
    }));
  },

  onAnswerSubmitted: (data) =>
    set({
      answerCount: data.count,
      totalCount: data.total,
      lastSeq: data.seq,
    }),

  onNarration: (data) => {
    log.info("narration_received", { trigger: data.trigger, text_len: data.text.length });
    return set({
      narrationText: data.text,
      narrationTrigger: data.trigger,
      lastSeq: data.seq,
    });
  },

  onBrainTestChallenge: (data) =>
    set({
      brainTestQuestion: data.question,
      brainTestChallengeIndex: data.challenge_index,
      brainTestChallengeType: data.challenge_type,
      brainTestOptions: data.options || [],
      phaseDeadline: data.sub_deadline,
      phaseDuration: data.phase_duration ?? 12,
      lastSeq: data.seq,
    }),

  onBrainTestResults: (data) =>
    set((s) => ({
      brainTestResults: data.results,
      brainTestScores: data.scores ?? null,
      scores: { ...s.scores, ...(data.scores || {}) },
      lastSeq: data.seq,
    })),

  onGameOver: (data) => {
    log.info("game_over", { winner: data.winner, winner_count: (data.winner_ids || []).length });
    return set({
      phase: "game_over",
      winner: data.winner,
      winnerIds: data.winner_ids || [],
      revealedPlayers: data.players,
      scores: data.scores || {},
      lastSeq: data.seq,
    });
  },

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

  onMatchupChallenge: (data) =>
    set({
      matchupIndex: data.matchup_index,
      matchupLeftId: data.left_player_id,
      matchupLeftAlias: data.left_alias,
      matchupLeftAnswer: data.left_answer,
      matchupRightId: data.right_player_id,
      matchupRightAlias: data.right_alias,
      matchupRightAnswer: data.right_answer,
      matchupPromptText: data.prompt_text,
      matchupMyVote: null,
      phaseDeadline: data.sub_deadline,
      phaseDuration: data.phase_duration ?? 12,
      lastSeq: data.seq,
    }),

  onMatchupResults: (data) =>
    set((s) => ({
      matchupResults: data,
      scores: { ...s.scores, ...(data.scores || {}) },
      lastSeq: data.seq,
    })),

  onFinalReveal: (data) => {
    log.info("final_reveal", { winner_count: (data.winner_ids || []).length, has_narration: !!data.narrator_text });
    return set({
      revealedPlayers: data.players,
      winnerIds: data.winner_ids || [],
      narrationText: data.narrator_text,
      narrationTrigger: "game_over",
      lastSeq: data.seq,
    });
  },

  onOpen: () => { log.info("sse_connected"); return set({ connectionStatus: "connected" }); },

  onError: () => { log.warn("sse_reconnecting"); return set({ connectionStatus: "reconnecting" }); },

  reset: () => set(initialState),
}));
