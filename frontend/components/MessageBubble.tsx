"use client";

import ReactMarkdown from "react-markdown";

export type Role = "user" | "assistant";

export interface Message {
  id: string;
  role: Role;
  content: string;
  streaming?: boolean;
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex w-full ${isUser ? "justify-end" : "justify-start"} mb-3`}
    >
      {!isUser && (
        <div className="mr-2.5 mt-0.5 flex-shrink-0">
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "#111",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 11,
              color: "#fff",
              fontWeight: 700,
              letterSpacing: "-0.5px",
            }}
          >
            C
          </div>
        </div>
      )}

      <div
        style={{
          maxWidth: "72%",
          borderRadius: isUser ? "18px 18px 4px 18px" : "18px 18px 18px 4px",
          padding: "10px 14px",
          background: isUser ? "#111111" : "#f5f5f5",
          border: isUser ? "none" : "1px solid #e8e8e8",
          color: isUser ? "#ffffff" : "#111111",
          fontSize: 14,
          lineHeight: 1.6,
          wordBreak: "break-word",
        }}
      >
        {isUser ? (
          <span style={{ whiteSpace: "pre-wrap" }}>{message.content}</span>
        ) : (
          <div className="prose-chat">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            {message.streaming && (
              <span
                style={{
                  display: "inline-block",
                  width: 6,
                  height: 14,
                  background: "#bbb",
                  borderRadius: 1,
                  marginLeft: 2,
                  verticalAlign: "middle",
                  animation: "blink 1s step-end infinite",
                }}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
