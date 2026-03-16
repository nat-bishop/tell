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
