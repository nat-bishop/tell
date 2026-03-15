"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { sendChat } from "@/api/actions";
import { Dialogue } from "./Dialogue";

export function Chat() {
  const { gameId, playerId, answers, messages, players } = useGameStore();
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50);
  }, []);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, autoScroll]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || !gameId || !playerId) return;
    setInput("");
    setAutoScroll(true);
    await sendChat(gameId, playerId, text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const answerEntries = Object.entries(answers).map(([pid, text]) => {
    const player = players.find((p) => p.id === pid);
    return { alias: player?.alias || "???", text };
  });

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="chat-scroll flex-1 space-y-7 overflow-y-auto pb-4"
      >
        {answerEntries.map((entry, i) => (
          <Dialogue key={`answer-${i}`} alias={entry.alias} text={entry.text} />
        ))}

        {answerEntries.length > 0 && messages.length > 0 && (
          <hr className="divider" />
        )}

        {messages.map((msg, i) => (
          <Dialogue
            key={`msg-${i}`}
            alias={msg.player_alias}
            text={msg.text}
          />
        ))}
      </div>

      <div
        className="sticky bottom-0 border-t pt-3 pb-4"
        style={{ borderColor: "var(--rule)", backgroundColor: "var(--page)" }}
      >
        <div className="flex items-end gap-3">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            className="flex-1 resize-none bg-transparent font-[family-name:var(--font-literary)] text-[1.1rem] leading-[1.6] min-h-[44px] outline-none"
            style={{ color: "var(--ink)" }}
            placeholder="speak..."
          />
          <button
            onClick={handleSend}
            className="shrink-0 font-[family-name:var(--font-literary)] text-[0.9rem] min-h-[44px] px-2 transition-opacity hover:opacity-70"
            style={{ color: "var(--dim)" }}
          >
            send &rarr;
          </button>
        </div>
      </div>
    </div>
  );
}
