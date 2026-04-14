"use client";

import { useEffect, useRef, useState } from "react";
import MessageBubble, { Message } from "@/components/MessageBubble";
import SuggestionChips from "@/components/SuggestionChips";
import { streamRecommendation, HistoryMessage } from "@/lib/api";

const WELCOME: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hello! I'm your CEAT Tyre advisor for 2-wheelers.\n\nTell me your motorcycle — brand, model, and variant — and I'll recommend the right CEAT tyre for you.",
};

let msgCounter = 1;
function newId() {
  return `msg_${msgCounter++}`;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [engineHistory, setEngineHistory] = useState<HistoryMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        160
      )}px`;
    }
  }, [input]);

  const sendMessage = async (text: string) => {
    const query = text.trim();
    if (!query || loading) return;

    setInput("");
    setLoading(true);

    // Add user message
    const userMsg: Message = { id: newId(), role: "user", content: query };
    const assistantId = newId();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      content: "",
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      let accumulated = "";
      for await (const token of streamRecommendation(query, engineHistory)) {
        accumulated += token;
        const captured = accumulated;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: captured, streaming: true }
              : m
          )
        );
      }
      // Mark streaming done and append to engine history
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, streaming: false } : m
        )
      );
      setEngineHistory((prev) => [
        ...prev,
        { role: "user", content: query },
        { role: "assistant", content: accumulated },
      ]);
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: "Sorry, something went wrong. Please try again.",
                streaming: false,
              }
            : m
        )
      );
    } finally {
      setLoading(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100dvh",
        background: "#ffffff",
        color: "#111111",
      }}
    >
      {/* Header */}
      <header
        style={{
          flexShrink: 0,
          padding: "14px 20px",
          borderBottom: "1px solid #ebebeb",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "#111",
            border: "none",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 13,
            fontWeight: 700,
            color: "#fff",
            letterSpacing: "-0.5px",
          }}
        >
          C
        </div>
        <div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "#111" }}>
            CEAT Tyre Advisor
          </div>
          <div style={{ fontSize: 11, color: "#999" }}>
            2-Wheeler Tyre Recommender
          </div>
        </div>
      </header>

      {/* Messages */}
      <main
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "20px 16px 8px",
          display: "flex",
          flexDirection: "column",
          maxWidth: 720,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {messages.map((m) => (
          <MessageBubble key={m.id} message={m} />
        ))}
        <div ref={bottomRef} />
      </main>

      {/* Suggestions — shown only when no user messages yet */}
      {messages.length === 1 && (
        <div style={{ padding: "0 0 12px" }}>
          <SuggestionChips onSelect={(t) => sendMessage(t)} />
        </div>
      )}

      {/* Input bar */}
      <footer
        style={{
          flexShrink: 0,
          padding: "12px 16px 20px",
          borderTop: "1px solid #ebebeb",
          background: "#ffffff",
        }}
      >
        <div
          style={{
            maxWidth: 720,
            margin: "0 auto",
            display: "flex",
            alignItems: "flex-end",
            gap: 10,
            background: "#f5f5f5",
            border: "1px solid #e0e0e0",
            borderRadius: 14,
            padding: "8px 8px 8px 14px",
          }}
        >
          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your motorcycle..."
            disabled={loading}
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              outline: "none",
              color: "#111111",
              fontSize: 14,
              resize: "none",
              lineHeight: 1.6,
              fontFamily: "inherit",
              paddingTop: 2,
              minHeight: 24,
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              border: "none",
              background:
                loading || !input.trim() ? "#e0e0e0" : "#111111",
              color: loading || !input.trim() ? "#999" : "#ffffff",
              cursor: loading || !input.trim() ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
              transition: "all 0.15s",
            }}
          >
            {loading ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="#555"
                  strokeWidth="2"
                />
                <path
                  d="M12 6v6l4 2"
                  stroke="#555"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            )}
          </button>
        </div>
        <p
          style={{
            textAlign: "center",
            fontSize: 11,
            color: "#bbb",
            marginTop: 10,
          }}
        >
          Made by Anupriyo Mandal
        </p>
      </footer>

      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </div>
  );
}
