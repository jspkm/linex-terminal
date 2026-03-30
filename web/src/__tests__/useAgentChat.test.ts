import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useAgentChat } from "@/app/hooks/useAgentChat";
import type { ApiRecord } from "@/lib/types";

const mockFetch = vi.fn();
global.fetch = mockFetch;

function makeDeps(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    learnInProgress: false,
    setLearnInProgress: vi.fn(),
    learnSource: "uploaded",
    setLearnSource: vi.fn(),
    setLearnK: vi.fn(),
    uploadedDatasets: [] as ApiRecord[],
    fetchCatalogList: vi.fn().mockResolvedValue(undefined),
    loadCatalog: vi.fn().mockResolvedValue(undefined),
    selectedCatalogVersion: "v_test",
    setSelectedCatalogVersion: vi.fn(),
    catalog: null,
    catalogList: [],
    optimizeInProgress: false,
    setOptimizeInProgress: vi.fn(),
    optimizationId: null as string | null,
    setOptimizationId: vi.fn(),
    optimizationState: null as ApiRecord | null,
    setOptimizationState: vi.fn(),
    optimizationPolling: false,
    setOptimizationPolling: vi.fn(),
    showOptimizationProgress: false,
    setShowOptimizationProgress: vi.fn(),
    setOptimizationStopPhase: vi.fn(),
    setOptimizationStarting: vi.fn(),
    optimizationStopRequestedRef: { current: false },
    optimizationCacheRef: { current: {} },
    savedOptimizations: [],
    selectedSavedOptimizationId: null as string | null,
    setSelectedSavedOptimizationId: vi.fn(),
    fetchSavedOptimizations: vi.fn().mockResolvedValue(undefined),
    incentiveSets: [],
    selectedIncentiveSetVersion: "",
    setSelectedIncentiveSetVersion: vi.fn(),
    selectedIncentiveSetDetail: null,
    setSelectedIncentiveSetDetail: vi.fn(),
    fetchIncentiveSets: vi.fn().mockResolvedValue(undefined),
    loadIncentiveSetDetail: vi.fn().mockResolvedValue(undefined),
    setPendingDeleteCatalog: vi.fn(),
    pendingDeleteCatalogRef: { current: null },
    setPendingDeleteIncentiveSet: vi.fn(),
    pendingDeleteIncentiveSetRef: { current: null },
    workflows: [],
    fetchWorkflows: vi.fn().mockResolvedValue(undefined),
    setActiveWorkflow: vi.fn(),
    setPendingDeleteWorkflow: vi.fn(),
    pendingDeleteWorkflowRef: { current: null },
    setPendingCreateWorkflow: vi.fn(),
    pendingCreateWorkflowRef: { current: null },
    setPendingWorkflowAction: vi.fn(),
    pendingWorkflowActionRef: { current: null },
    setPendingEditWorkflow: vi.fn(),
    pendingEditWorkflowRef: { current: null },
    setGenError: vi.fn(),
    ...overrides,
  } as Parameters<typeof useAgentChat>[0];
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("useAgentChat", () => {
  it("initializes with empty state", () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));
    expect(result.current.agentChatMessages).toEqual([]);
    expect(result.current.agentChatDraft).toBe("");
    expect(result.current.agentChatLoading).toBe(false);
    expect(result.current.gridCustomColumns).toEqual([]);
  });

  it("executes add_column action", async () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "add_column", label: "ROI", formula: "lift / portfolio_cost", format: "ratio", totals: "avg" },
      ]);
    });

    expect(result.current.gridCustomColumns).toHaveLength(1);
    expect(result.current.gridCustomColumns[0].label).toBe("ROI");
    expect(result.current.gridCustomColumns[0].format).toBe("ratio");
  });

  it("executes remove_column action", async () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));

    // Add then remove
    await act(async () => {
      await result.current.executeAgentActions([
        { type: "add_column", label: "TEST", formula: "lift", format: "dollar" },
      ]);
    });
    expect(result.current.gridCustomColumns).toHaveLength(1);

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "remove_column", label: "TEST" },
      ]);
    });
    expect(result.current.gridCustomColumns).toHaveLength(0);
  });

  it("replaces column with same label", async () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "add_column", label: "METRIC", formula: "lift", format: "dollar" },
      ]);
    });
    await act(async () => {
      await result.current.executeAgentActions([
        { type: "add_column", label: "METRIC", formula: "portfolio_cost", format: "dollar" },
      ]);
    });

    expect(result.current.gridCustomColumns).toHaveLength(1);
    expect(result.current.gridCustomColumns[0].exprSource).toBe("portfolio_cost");
  });

  it("rejects invalid formula", async () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "add_column", label: "BAD", formula: "alert('xss')", format: "number" },
      ]);
    });

    expect(result.current.gridCustomColumns).toHaveLength(0);
  });

  it("executes save_report_config action", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ config_id: "rc_abc", name: "Test Report" }),
    });

    const { result } = renderHook(() => useAgentChat(makeDeps()));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "save_report_config", name: "Test Report" },
      ]);
    });

    // Should have a chat message about saving
    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("Test Report"))).toBe(true);
  });

  it("executes list_report_configs action", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        configs: [
          { config_id: "rc_1", name: "My Report", columns: [{ label: "ROI" }], created_at: "2026-01-01" },
        ],
      }),
    });

    const { result } = renderHook(() => useAgentChat(makeDeps()));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "list_report_configs" },
      ]);
    });

    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("My Report"))).toBe(true);
  });

  it("executes run_what_if action", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        overrides: "uptake=20%",
        profiles: [{ profile_id: "P0", base: { lift: 100 }, what_if: { lift: 80 }, delta_lift: -20 }],
        total_delta_lift: -20,
      }),
    });

    const deps = makeDeps({ optimizationId: "mc_test" });
    const { result } = renderHook(() => useAgentChat(deps));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "run_what_if", uptake_override: 0.2 },
      ]);
    });

    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("What-if"))).toBe(true);
  });

  it("handles run_what_if without optimization", async () => {
    const deps = makeDeps({ optimizationId: null });
    const { result } = renderHook(() => useAgentChat(deps));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "run_what_if", uptake_override: 0.1 },
      ]);
    });

    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("No optimization"))).toBe(true);
  });

  it("executes create_workflow action", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ workflow_id: "wf_new", name: "Test WF" }),
    });

    const deps = makeDeps();
    const { result } = renderHook(() => useAgentChat(deps));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "create_workflow", name: "Test WF", description: "A test", detail: "Detail text" },
      ]);
    });

    expect(deps.fetchWorkflows).toHaveBeenCalled();
  });

  it("executes list_workflows action", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ workflows: [{ name: "My WF", description: "Custom", workflow_id: "wf_1" }] }),
    });

    const deps = makeDeps();
    (deps as Record<string, unknown>).setWorkflows = vi.fn();
    const { result } = renderHook(() => useAgentChat(deps));

    // list_workflows appends to the last agent message, so seed one first
    act(() => {
      result.current.setAgentChatMessages([{ id: "seed", role: "agent" as const, text: "Here are your workflows:", submittedAt: "" }]);
    });

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "list_workflows" },
      ]);
    });

    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("Optimize portfolio"))).toBe(true);
  });

  it("executes list_incentive_sets action", async () => {
    const deps = makeDeps({
      incentiveSets: [
        { version: "is_1", name: "Default Set", is_default: true, incentive_count: 10 },
      ],
    });
    const { result } = renderHook(() => useAgentChat(deps));

    await act(async () => {
      await result.current.executeAgentActions([
        { type: "list_incentive_sets" },
      ]);
    });

    const msgs = result.current.agentChatMessages;
    expect(msgs.some((m) => m.text.includes("Default Set"))).toBe(true);
  });

  it("sets and clears draft", () => {
    const { result } = renderHook(() => useAgentChat(makeDeps()));

    act(() => {
      result.current.setAgentChatDraft("hello agent");
    });
    expect(result.current.agentChatDraft).toBe("hello agent");

    act(() => {
      result.current.setAgentChatDraft("");
    });
    expect(result.current.agentChatDraft).toBe("");
  });
});
