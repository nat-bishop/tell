import { apiFetch } from "./client";

export interface CreateGameResponse {
  game_id: string;
  join_url: string;
}

export interface JoinGameResponse {
  player_id: string;
  alias: string;
  game_id: string;
}

export function createGame(): Promise<CreateGameResponse> {
  return apiFetch<CreateGameResponse>("/games", { method: "POST" });
}

export function joinGame(
  gameId: string,
  playerName: string,
): Promise<JoinGameResponse> {
  return apiFetch<JoinGameResponse>(`/games/${gameId}/join`, {
    method: "POST",
    body: JSON.stringify({ player_name: playerName }),
  });
}

export function startGame(
  gameId: string,
  playerId: string,
  aiCount: number = 2,
): Promise<void> {
  return apiFetch(`/games/${gameId}/start`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, ai_count: aiCount }),
  });
}

export function submitAnswer(
  gameId: string,
  playerId: string,
  answer: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/answer`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, answer }),
  });
}

export function submitQuestion(
  gameId: string,
  playerId: string,
  question: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/question`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, question }),
  });
}

export function submitResponse(
  gameId: string,
  playerId: string,
  response: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/respond`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, response }),
  });
}

export function nominate(
  gameId: string,
  playerId: string,
  targetId: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/nominate`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, target_id: targetId }),
  });
}

export function castVote(
  gameId: string,
  playerId: string,
  targetIds: string[],
): Promise<void> {
  return apiFetch(`/games/${gameId}/vote`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, target_ids: targetIds }),
  });
}

export function castComedyVote(
  gameId: string,
  playerId: string,
  targetId: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/comedy-vote`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, target_id: targetId }),
  });
}

export function submitBrainTestAnswer(
  gameId: string,
  playerId: string,
  answer: string,
  challengeIndex: number,
): Promise<void> {
  return apiFetch(`/games/${gameId}/brain-test-answer`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      answer,
      challenge_index: challengeIndex,
    }),
  });
}

export function submitChainWord(
  gameId: string,
  playerId: string,
  word: string,
  roundIndex: number,
): Promise<void> {
  return apiFetch(`/games/${gameId}/chain-word`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      word,
      round_index: roundIndex,
    }),
  });
}

export function sendDiscussionMessage(
  gameId: string,
  playerId: string,
  message: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/discussion-message`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId, message }),
  });
}

// --- Matchmaking ---

export interface MatchmakingJoinResponse {
  player_id: string;
  alias: string;
  position: number;
}

export function joinMatchmaking(
  playerName: string,
): Promise<MatchmakingJoinResponse> {
  return apiFetch<MatchmakingJoinResponse>("/matchmaking/join", {
    method: "POST",
    body: JSON.stringify({ player_name: playerName }),
  });
}

export function leaveMatchmaking(playerId: string): Promise<void> {
  return apiFetch("/matchmaking/leave", {
    method: "POST",
    body: JSON.stringify({ player_id: playerId }),
  });
}
