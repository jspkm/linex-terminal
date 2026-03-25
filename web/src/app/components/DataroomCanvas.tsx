"use client";

import { useState } from "react";
import { C } from "./theme";

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

interface DataItem {
  name: string;
  id: string;
  type: string;
  source: string;
  published: string;
  synced: string;
}

const samplePortfolio: DataItem[] = [
  { name: "Kayne Small Cap Portfolio.pdf", id: "1330488", type: "Factsheet", source: "J.P. Morgan", published: "03/31/2024", synced: "01/28/26 19:02" },
  { name: "Kayne Small&Mid Cap Deck.pdf", id: "1330489", type: "Company Presentation", source: "J.P. Morgan", published: "12/05/2023", synced: "01/28/26 19:02" },
  { name: "JP Morgan US Tech Leaders Perf.pdf", id: "1330490", type: "Factsheet", source: "J.P. Morgan", published: "03/31/2024", synced: "01/28/26 19:02" },
  { name: "JP Morgan Innovators Strategy.pdf", id: "1330283", type: "Strategy Profile", source: "J.P. Morgan", published: "06/30/2024", synced: "01/28/26 18:53" },
  { name: "JP Morgan US Tech Leaders Deck.pdf", id: "1330284", type: "Company Presentation", source: "J.P. Morgan", published: "09/01/2022", synced: "01/28/26 18:53" },
  { name: "JP Morgan Digital Evolution Profile.pdf", id: "1330244", type: "Strategy Profile", source: "J.P. Morgan", published: "01/01/2024", synced: "01/28/26 18:49" },
  { name: "JP Morgan Digital Evolution Perf.pdf", id: "1330237", type: "Fund Performance", source: "J.P. Morgan", published: "06/30/2024", synced: "01/28/26 18:34" },
];

const myUploads: DataItem[] = [
  { name: "Q1 2026 Retail Transactions.csv", id: "u-001", type: "Transaction Data", source: "Uploaded", published: "—", synced: "03/22/26 13:45" },
  { name: "Holiday 2025 Portfolio.csv", id: "u-002", type: "Transaction Data", source: "Uploaded", published: "—", synced: "03/15/26 09:30" },
];

const sampleTransactions: DataItem[] = [
  { name: "demo_user_TX-4821.csv", id: "t-001", type: "User Transactions", source: "Test Data", published: "—", synced: "Built-in" },
  { name: "demo_user_TX-3192.csv", id: "t-002", type: "User Transactions", source: "Test Data", published: "—", synced: "Built-in" },
  { name: "demo_user_TX-7744.csv", id: "t-003", type: "User Transactions", source: "Test Data", published: "—", synced: "Built-in" },
  { name: "demo_user_TX-1028.csv", id: "t-004", type: "User Transactions", source: "Test Data", published: "—", synced: "Built-in" },
  { name: "demo_user_TX-5593.csv", id: "t-005", type: "User Transactions", source: "Test Data", published: "—", synced: "Built-in" },
];

const columns = ["Document Name", "ID", "Document Type", "Source", "Published At", "Synced At (EDT)", "Status"];

export default function DataroomCanvas() {
  const [expandedFolder, setExpandedFolder] = useState<Record<string, boolean>>({
    sample: true,
    uploads: false,
    transactions: true,
  });

  const toggle = (key: string) =>
    setExpandedFolder((prev) => ({ ...prev, [key]: !prev[key] }));

  const renderRow = (item: DataItem, indent = false) => (
    <tr key={item.id} style={{ borderBottom: `1px solid ${C.border}22` }}>
      <td style={{ padding: "8px 12px", paddingLeft: indent ? 40 : 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: 12,
              color: item.name.endsWith(".pdf")
                ? C.danger
                : item.name.endsWith(".csv")
                ? C.accent
                : C.blue,
            }}
          >
            {item.name.endsWith(".pdf") ? "📕" : "📊"}
          </span>
          <span style={{ fontSize: 11, color: C.blue, cursor: "pointer" }}>{item.name}</span>
        </div>
      </td>
      <td style={{ padding: "8px 10px", color: C.muted, fontFamily: "monospace", fontSize: 10 }}>
        {item.id}
      </td>
      <td style={{ padding: "8px 10px", color: C.textSec, fontSize: 11 }}>{item.type}</td>
      <td style={{ padding: "8px 10px", color: C.textSec, fontSize: 11 }}>{item.source}</td>
      <td style={{ padding: "8px 10px", color: C.muted, fontSize: 10 }}>{item.published}</td>
      <td style={{ padding: "8px 10px", color: C.muted, fontSize: 10 }}>{item.synced}</td>
      <td style={{ padding: "8px 10px", textAlign: "center" }}>
        <span style={{ color: C.accent }}>✓</span>
      </td>
    </tr>
  );

  const renderFolderRow = (label: string, key: string, count: number) => (
    <tr
      key={key}
      onClick={() => toggle(key)}
      style={{ cursor: "pointer", borderBottom: `1px solid ${C.border}33` }}
    >
      <td colSpan={7} style={{ padding: "10px 12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: C.muted, fontSize: 11 }}>
            {expandedFolder[key] ? "▾" : "▸"}
          </span>
          <span style={{ fontSize: 13 }}>📁</span>
          <span style={{ fontSize: 12, color: C.text, fontWeight: 500 }}>{label}</span>
          <span style={{ fontSize: 10, color: C.muted }}>({count})</span>
          <span style={{ marginLeft: "auto", color: C.accent }}>✓</span>
        </div>
      </td>
    </tr>
  );

  return (
    <div style={{ height: "100%", overflow: "auto", padding: "18px 24px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 18,
        }}
      >
        <div>
          <span style={{ fontSize: 14, fontWeight: 600, color: C.accent, letterSpacing: "0.06em" }}>
            All Data Rooms
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
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
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 13 }}>↑</span> Upload Portfolio
          </button>
          <button
            style={{
              fontSize: 10,
              color: C.blue,
              background: `${C.blue}10`,
              border: `1px solid ${C.blue}44`,
              borderRadius: 2,
              padding: "6px 14px",
              cursor: "pointer",
              fontFamily: "inherit",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ fontSize: 13 }}>↑</span> Upload User Data
          </button>
        </div>
      </div>

      <div
        style={{
          border: `1px solid ${C.border}`,
          borderRadius: 2,
          background: C.surface,
          overflow: "hidden",
        }}
      >
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              {columns.map((h, i) => (
                <th
                  key={h}
                  style={{
                    textAlign: i === 6 ? "center" : "left",
                    padding: "9px 12px",
                    color: C.muted,
                    fontWeight: 600,
                    fontSize: 9,
                    letterSpacing: "0.05em",
                    borderBottom: `1px solid ${C.border}`,
                  }}
                >
                  {h} {i < 6 && <span style={{ color: C.borderLt }}>↓</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {renderFolderRow("Sample Portfolio", "sample", samplePortfolio.length)}
            {expandedFolder.sample && samplePortfolio.map((item) => renderRow(item, true))}

            {renderFolderRow("Sample User Transactions", "transactions", sampleTransactions.length)}
            {expandedFolder.transactions &&
              sampleTransactions.map((item) => renderRow(item, true))}

            {renderFolderRow("My Uploads", "uploads", myUploads.length)}
            {expandedFolder.uploads && myUploads.map((item) => renderRow(item, true))}
          </tbody>
        </table>
      </div>

      {/* Drop zone */}
      <div
        style={{
          marginTop: 16,
          border: `2px dashed ${C.borderLt}`,
          borderRadius: 2,
          padding: "24px 20px",
          textAlign: "center",
          cursor: "pointer",
          background: C.accentBg,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = C.accent + "88";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = C.borderLt;
        }}
      >
        <div style={{ fontSize: 20, marginBottom: 6 }}>↑</div>
        <div style={{ fontSize: 12, color: C.textSec, marginBottom: 4 }}>
          Drop files here to upload
        </div>
        <div style={{ fontSize: 10, color: C.muted }}>
          Supports: .csv, .pdf, .xlsx — Portfolio data or user transaction files
        </div>
      </div>
    </div>
  );
}
