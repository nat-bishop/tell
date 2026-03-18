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
  | "brain_test"
  | "brain_test_results";

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
  winner_ids: string[];
  is_host: boolean;
  phase_deadline: string | null;
  phase_duration: number | null;
  writing_begins_at?: string | null;
  action_starts_at?: string | null;
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
  action_starts_at?: string;
  discuss_starts_at?: string;
  vote_starts_at?: string;
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
  winner_ids: string[];
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
  scores: Record<string, number> | null;
  winner_id: string | null;
  winner_alias: string | null;
  ability_awarded: string | null;
}

export interface ComedyWinnerData {
  seq: number;
  winner_id: string;
  winner_alias: string;
  vote_count: number;
}

export interface DiscussionMessageData {
  seq: number;
  sender_id: string;
  sender_alias: string;
  message: string;
}

export interface AbilityAwardedData {
  seq: number;
  holder_id: string;
  holder_alias: string;
  ability_type: string;
}

export interface ScanResultData {
  seq: number;
  results: Array<{
    player_id: string;
    alias: string;
    claimed_role: string;
  }>;
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

  // Interstitial
  actionStartsAt: string | null;

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

  // Cumulative context for narrative
  totalRounds: number;
  lastEliminationWasHuman: boolean | null;
  humansEliminated: number;
  aisEliminated: number;

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
    question: string;
    options: string[];
    selected_index: number;
    correct_index: number;
    challenge_type: string;
  }>> | null;
  // Comedy
  comedyWinnerAlias: string | null;
  comedyWinnerVotes: number;
  myComedyVote: string | null;

  // Discussion
  discussionMessages: Array<{ sender_id: string; sender_alias: string; message: string }>;
  myDiscussionCount: number;
  discussStartsAt: string | null;
  voteStartsAt: string | null;

  // Abilities
  activeAbilityHolder: string | null;
  activeAbilityHolderAlias: string | null;
  activeAbilityType: string | null;
  scanResults: Array<{ player_id: string; alias: string; claimed_role: string }> | null;

  // Brain Test scores
  brainTestScores: Record<string, number> | null;
  brainTestWinnerId: string | null;
  brainTestWinnerAlias: string | null;
  brainTestAbilityAwarded: string | null;

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
  onNarration: (data: NarrationData) => void;
  onComedyWinner: (data: ComedyWinnerData) => void;
  onBrainTestChallenge: (data: BrainTestChallengeData) => void;
  onBrainTestResults: (data: BrainTestResultsData) => void;
  onDiscussionMessage: (data: DiscussionMessageData) => void;
  onAbilityAwarded: (data: AbilityAwardedData) => void;
  onScanResult: (data: ScanResultData) => void;
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
  actionStartsAt: null as string | null,
  eliminatedId: null as string | null,
  eliminatedAlias: null as string | null,
  wasHuman: null as boolean | null,
  eliminationVoteCount: 0,
  eliminationTie: false,
  eliminationTieMessage: null as string | null,
  eliminationNoVotes: false,
  voteResults: null as Record<string, string[]> | null,
  voteTallies: null as Record<string, number> | null,
  totalRounds: 0,
  lastEliminationWasHuman: null as boolean | null,
  humansEliminated: 0,
  aisEliminated: 0,
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
  comedyWinnerAlias: null as string | null,
  comedyWinnerVotes: 0,
  myComedyVote: null as string | null,
  discussionMessages: [] as Array<{ sender_id: string; sender_alias: string; message: string }>,
  myDiscussionCount: 0,
  discussStartsAt: null as string | null,
  voteStartsAt: null as string | null,
  activeAbilityHolder: null as string | null,
  activeAbilityHolderAlias: null as string | null,
  activeAbilityType: null as string | null,
  scanResults: null as Array<{ player_id: string; alias: string; claimed_role: string }> | null,
  brainTestScores: null as Record<string, number> | null,
  brainTestWinnerId: null as string | null,
  brainTestWinnerAlias: null as string | null,
  brainTestAbilityAwarded: null as string | null,
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
      winnerIds: data.winner_ids || [],
      isHost: data.is_host,
      phaseDeadline: data.phase_deadline,
      phaseDuration: data.phase_duration ?? null,
      writingBeginsAt: data.writing_begins_at ?? null,
      actionStartsAt: data.action_starts_at ?? null,
      lastSeq: data.seq,
      connectionStatus: "connected",
      myVotes: data.my_votes || [],
      myQuestionSubmitted: false,
      myResponseSubmitted: false,
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
    set((s) => ({
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
      totalCount: data.phase === "prompt"
        ? s.players.filter((p) => p.is_alive).length
        : 0,
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
      narrationText: null,
      narrationTrigger: null,
      comedyWinnerAlias: null,
      comedyWinnerVotes: 0,
      myComedyVote: null,
      // Discussion reset
      discussionMessages: [],
      myDiscussionCount: 0,
      discussStartsAt: data.discuss_starts_at ?? null,
      voteStartsAt: data.vote_starts_at ?? null,
      // Scan reset per round
      scanResults: null,
      // Brain test reset
      brainTestQuestion: null,
      brainTestChallengeIndex: 0,
      brainTestChallengeType: null,
      brainTestOptions: [],
      brainTestResults: null,
      brainTestScores: null,
      brainTestWinnerId: null,
      brainTestWinnerAlias: null,
      brainTestAbilityAwarded: null,
    })),

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

  onNarration: (data) =>
    set({
      narrationText: data.text,
      narrationTrigger: data.trigger,
      lastSeq: data.seq,
    }),

  onComedyWinner: (data) =>
    set({
      comedyWinnerAlias: data.winner_alias,
      comedyWinnerVotes: data.vote_count,
      lastSeq: data.seq,
    }),

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
    set({
      brainTestResults: data.results,
      brainTestScores: data.scores ?? null,
      brainTestWinnerId: data.winner_id ?? null,
      brainTestWinnerAlias: data.winner_alias ?? null,
      brainTestAbilityAwarded: data.ability_awarded ?? null,
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
      lastEliminationWasHuman: data.was_human,
      humansEliminated: s.humansEliminated + (data.was_human === true ? 1 : 0),
      aisEliminated: s.aisEliminated + (data.was_human === false && data.eliminated_id ? 1 : 0),
      totalRounds: Math.max(s.totalRounds, s.roundNumber),
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
      winnerIds: data.winner_ids || [],
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

  onDiscussionMessage: (data) =>
    set((s) => ({
      discussionMessages: [
        ...s.discussionMessages,
        { sender_id: data.sender_id, sender_alias: data.sender_alias, message: data.message },
      ],
      myDiscussionCount:
        data.sender_id === s.playerId ? s.myDiscussionCount + 1 : s.myDiscussionCount,
      lastSeq: data.seq,
    })),

  onAbilityAwarded: (data) =>
    set({
      activeAbilityHolder: data.holder_id,
      activeAbilityHolderAlias: data.holder_alias,
      activeAbilityType: data.ability_type,
      lastSeq: data.seq,
    }),

  onScanResult: (data) =>
    set({
      scanResults: data.results,
      lastSeq: data.seq,
    }),

  onOpen: () => set({ connectionStatus: "connected" }),

  onError: () => set({ connectionStatus: "reconnecting" }),

  reset: () => set(initialState),
}));
