"use client";

import { C, type View } from "./theme";

interface Template {
  id: string;
  cat: string;
  text: string;
  icon: string;
  desc: string;
}

function Badge({ text, color = C.accent }: { text: string; color?: string }) {
  return (
    <span
      style={{
        fontSize: 9,
        color,
        background: `${color}18`,
        border: `1px solid ${color}33`,
        borderRadius: 2,
        padding: "2px 7px",
        fontFamily: "monospace",
      }}
    >
      {text}
    </span>
  );
}

interface WorkflowCanvasProps {
  onTemplate: (template: Template) => void;
}

const templates: Template[] = [
  {
    id: "t0",
    cat: "Profile Generator",
    text: "Optimize portfolio",
    icon: "🚀",
    desc: "Learn behavioral profiles from transaction data using clustering, then derive optimal incentive program through simulation.",
  },
  {
    id: "t1",
    cat: "User Profiler",
    text: "Profile test user TX-4821 and match credit cards",
    icon: "⚡",
    desc: "Analyze a test user's behavioral axes and get card recommendations ranked by fit score.",
  },
  {
    id: "t2",
    cat: "User Profiler",
    text: "Upload my Q1 transactions and profile the customer",
    icon: "📄",
    desc: "Upload a CSV of transaction data, run behavioral profiling, and match to existing catalog profiles.",
  },
  {
    id: "t3",
    cat: "Profile Generator",
    text: "Learn 10 behavioral profiles from Q1 Retail portfolio",
    icon: "🧠",
    desc: "Run K-Means clustering on a transaction dataset to discover canonical behavioral profiles.",
  },
  {
    id: "t4",
    cat: "Profile Generator",
    text: "Optimize catalog with default incentive set and show results",
    icon: "📈",
    desc: "Run convergence-based optimization to find the optimal incentive assignment per profile.",
  },
  {
    id: "t5",
    cat: "User Profiler",
    text: "Compare two test users and explain behavioral differences",
    icon: "🔀",
    desc: "Profile two users side by side and highlight divergences across all four behavioral axes.",
  },
  {
    id: "t6",
    cat: "Profile Generator",
    text: "Re-learn profiles with K=6 and compare to previous catalog",
    icon: "🔄",
    desc: "Generate a new catalog with different K and diff it against the existing version.",
  },
];

const suggested = [
  {
    id: "s1",
    cat: "Manager Selection",
    text: "The digital evolution strategy has significant exposure to semiconductors. Pull the latest earnings...",
    icon: "◇",
    desc: "",
  },
  {
    id: "s2",
    cat: "Manager Selection",
    text: "Evaluate whether the JPM tech leaders strategy would have outperformed during the 2022 drawdown",
    icon: "◇",
    desc: "",
  },
  {
    id: "s3",
    cat: "Client Communication",
    text: "Create a onepager of the Innovators Strategy for a client pitch meeting tomorrow",
    icon: "◇",
    desc: "",
  },
  {
    id: "s4",
    cat: "Client Communication",
    text: "I'm meeting with a client tomorrow who's interested in small cap value — prep talking points",
    icon: "◇",
    desc: "",
  },
];

export default function WorkflowCanvas({ onTemplate }: WorkflowCanvasProps) {
  return (
    <div style={{ height: "100%", overflow: "auto", padding: "24px 28px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 20,
        }}
      >
        <div>
          <span style={{ fontSize: 14, fontWeight: 600, color: C.accent, letterSpacing: "0.06em" }}>
            Workflow Templates
          </span>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
            Click a template to start a workflow, or describe your own.
          </div>
        </div>
        <button
          style={{
            fontSize: 10,
            color: C.accent,
            background: C.accentBg,
            border: `1px solid ${C.accent}44`,
            borderRadius: 2,
            padding: "6px 14px",
            cursor: "pointer",
            fontFamily: "inherit",
          }}
        >
          + New Template
        </button>
      </div>

      {/* LINEX Templates */}
      <div style={{ marginBottom: 28 }}>
        <div
          style={{
            fontSize: 10,
            color: C.accent,
            letterSpacing: "0.08em",
            marginBottom: 10,
            fontWeight: 600,
          }}
        >
          LINEX WORKFLOWS
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {templates.map((t) => (
            <div
              key={t.id}
              onClick={() => onTemplate(t)}
              style={{
                border: `1px solid ${C.border}`,
                borderRadius: 2,
                padding: "14px 16px",
                background: C.surface,
                cursor: "pointer",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = C.accent + "66";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = C.border;
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                <span style={{ fontSize: 18, marginTop: 1 }}>{t.icon}</span>
                <div style={{ flex: 1 }}>
                  <p
                    style={{
                      fontSize: 12,
                      color: C.text,
                      margin: "0 0 4px",
                      lineHeight: 1.4,
                      fontWeight: 500,
                    }}
                  >
                    {t.text}
                  </p>
                  <p style={{ fontSize: 10, color: C.muted, margin: "0 0 8px", lineHeight: 1.4 }}>
                    {t.desc}
                  </p>
                  <Badge text={t.cat} color={C.accent} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Suggested Research */}
      <div>
        <div
          style={{
            fontSize: 10,
            color: C.amber,
            letterSpacing: "0.08em",
            marginBottom: 10,
            fontWeight: 600,
          }}
        >
          SUGGESTED RESEARCH
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {suggested.map((t) => (
            <div
              key={t.id}
              onClick={() => onTemplate(t)}
              style={{
                border: `1px solid ${C.border}`,
                borderRadius: 2,
                padding: "14px 16px",
                background: C.surface,
                cursor: "pointer",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = C.amber + "55";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = C.border;
              }}
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                <span style={{ fontSize: 14, color: C.amber }}>◇</span>
                <div>
                  <p style={{ fontSize: 11, color: C.text, margin: "0 0 6px", lineHeight: 1.4 }}>
                    {t.text}
                  </p>
                  <Badge text={t.cat} color={C.amber} />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
