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
          <span style={{ fontSize: 12, fontWeight: 700, color: "#00aaff", letterSpacing: "0.05em" }}>
            Workflow
          </span>
          <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>
            Click a workflow card to activate it, or describe your own.
          </div>
        </div>
      </div>

      {/* LINEX Templates */}
      <div style={{ marginBottom: 28 }}>
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
              <div>
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
                  <p style={{ fontSize: 10, color: C.muted, margin: 0, lineHeight: 1.4 }}>
                    {t.desc}
                  </p>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  );
}
