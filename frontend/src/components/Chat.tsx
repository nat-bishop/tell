"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useGameStore } from "@/hooks/useGameStore";
import { useAnswerEntries } from "@/hooks/useAnswerEntries";
import { sendChat } from "@/api/actions";
import { Dialogue } from "./Dialogue";

export function Chat({ spectator = false }: { spectator?: boolean }) {
  const { gameId, playerId, messages } = useGameStore();
  const answerEntries = useAnswerEntries();
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

      {!spectator && (
        <div className="sticky bottom-0 border-t pt-3 pb-4 border-rule bg-page">
          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              className="flex-1 resize-none bg-transparent font-literary text-[1.1rem] leading-[1.6] min-h-[44px] text-ink outline-none"
              placeholder="speak..."
            />
            <button
              onClick={handleSend}
              className="shrink-0 font-literary text-[0.9rem] min-h-[44px] px-2 text-dim transition-opacity hover:opacity-70"
            >
              send &rarr;
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
