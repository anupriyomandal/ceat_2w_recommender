"use client";

const SUGGESTIONS = [
  "Bajaj Pulsar NS 200",
  "Hero Splendor Plus",
  "Royal Enfield Classic 350",
  "Honda Unicorn 160",
  "Yamaha R15 V4",
  "KTM Duke 390",
];

export default function SuggestionChips({
  onSelect,
}: {
  onSelect: (text: string) => void;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        justifyContent: "center",
        padding: "0 16px 4px",
      }}
    >
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          onClick={() => onSelect(`What tyre fits a ${s}?`)}
          style={{
            background: "transparent",
            border: "1px solid #d8d8d8",
            borderRadius: 20,
            padding: "6px 14px",
            fontSize: 12,
            color: "#666",
            cursor: "pointer",
            transition: "all 0.15s",
            whiteSpace: "nowrap",
          }}
          onMouseEnter={(e) => {
            (e.target as HTMLButtonElement).style.borderColor = "#999";
            (e.target as HTMLButtonElement).style.color = "#111";
          }}
          onMouseLeave={(e) => {
            (e.target as HTMLButtonElement).style.borderColor = "#d8d8d8";
            (e.target as HTMLButtonElement).style.color = "#666";
          }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
