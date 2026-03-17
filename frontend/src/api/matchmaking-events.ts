import { SSE_URL } from "./client";

export interface LobbyStatusData {
  event_type: "lobby_status";
  seq: number;
  human_count: number;
  countdown_seconds: number | null;
  message: string;
}

export interface GameAssignedData {
  event_type: "game_assigned";
  seq: number;
  game_id: string;
}

export interface MatchmakingCallbacks {
  onLobbyStatus: (data: LobbyStatusData) => void;
  onGameAssigned: (data: GameAssignedData) => void;
}

export function connectMatchmakingEvents(
  playerId: string,
  callbacks: MatchmakingCallbacks,
): { close: () => void } {
  const url = `${SSE_URL}/matchmaking/events?player_id=${playerId}`;
  const es = new EventSource(url);

  es.addEventListener("lobby_status", (e: MessageEvent) => {
    try {
      callbacks.onLobbyStatus(JSON.parse(e.data));
    } catch {
      console.error("Failed to parse lobby_status event", e.data);
    }
  });

  es.addEventListener("game_assigned", (e: MessageEvent) => {
    try {
      callbacks.onGameAssigned(JSON.parse(e.data));
    } catch {
      console.error("Failed to parse game_assigned event", e.data);
    }
  });

  es.onerror = () => {
    console.warn("Matchmaking SSE error, will auto-reconnect");
  };

  return { close: () => es.close() };
}
