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
): Promise<void> {
  return apiFetch(`/games/${gameId}/start`, {
    method: "POST",
    body: JSON.stringify({ player_id: playerId }),
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

export function submitBrainTestAnswer(
  gameId: string,
  playerId: string,
  selectedIndex: number,
  challengeIndex: number,
): Promise<void> {
  return apiFetch(`/games/${gameId}/brain-test-answer`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      selected_index: selectedIndex,
      challenge_index: challengeIndex,
    }),
  });
}

export function submitVote(
  gameId: string,
  playerId: string,
  votedForPlayerId: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/vote`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      voted_for_player_id: votedForPlayerId,
    }),
  });
}

export function submitWagerGuess(
  gameId: string,
  playerId: string,
  questionIndex: number,
  value: number,
): Promise<void> {
  return apiFetch(`/games/${gameId}/wager-guess`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      question_index: questionIndex,
      value,
    }),
  });
}

export function submitWagerBet(
  gameId: string,
  playerId: string,
  questionIndex: number,
  targetPlayerId: string,
): Promise<void> {
  return apiFetch(`/games/${gameId}/wager-bet`, {
    method: "POST",
    body: JSON.stringify({
      player_id: playerId,
      question_index: questionIndex,
      target_player_id: targetPlayerId,
    }),
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
