const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HistoryMessage {
  role: "user" | "assistant";
  content: string;
}

export async function* streamRecommendation(
  query: string,
  history: HistoryMessage[] = []
): AsyncGenerator<string> {
  const res = await fetch(`${API_URL}/recommend/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, history }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`API error: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (!raw) continue;

      try {
        const parsed = JSON.parse(raw);
        if (parsed.error) throw new Error(parsed.error);
        if (parsed.done) return;
        if (parsed.token) yield parsed.token;
      } catch {
        // malformed chunk — ignore
      }
    }
  }
}
