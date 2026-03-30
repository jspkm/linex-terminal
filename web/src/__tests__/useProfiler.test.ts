import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useProfiler } from "@/app/hooks/useProfiler";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
  // Default: return empty test users for the auto-fetch in useEffect
  mockFetch.mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ user_ids: [] }),
  });
});

describe("useProfiler", () => {
  it("initializes with default state", () => {
    const { result } = renderHook(() => useProfiler());
    expect(result.current.profilerTab).toBe("test");
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe("");
    expect(result.current.results).toBeNull();
    expect(result.current.file).toBeNull();
  });

  it("fetches test users on mount", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ user_ids: ["user_1", "user_2"] }),
    });

    const { result } = renderHook(() => useProfiler());

    // Wait for useEffect to run
    await act(async () => {
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.testUserIds).toEqual(["user_1", "user_2"]);
    expect(result.current.selectedUserId).toBe("user_1");
  });

  it("analyzes a test user", async () => {
    // First call: list_test_users (useEffect)
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ user_ids: ["user_1"] }),
    });

    const { result } = renderHook(() => useProfiler());
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });

    // Second call: analyze_test_user
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ features: { spend: 100 }, recommendations: [] }),
    });

    await act(async () => {
      await result.current.analyzeTestUser();
    });

    expect(result.current.results).not.toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("handles analyze error", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ user_ids: ["user_1"] }),
    });

    const { result } = renderHook(() => useProfiler());
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });

    mockFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: "User not found" }),
    });

    await act(async () => {
      await result.current.analyzeTestUser();
    });

    expect(result.current.error).toBe("User not found");
    expect(result.current.loading).toBe(false);
  });

  it("stops profiler process", async () => {
    const { result } = renderHook(() => useProfiler());

    act(() => {
      result.current.stopProfilerProcess();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe("");
    expect(result.current.results).toBeNull();
  });

  it("sets profiler tab", () => {
    const { result } = renderHook(() => useProfiler());
    act(() => {
      result.current.setProfilerTab("upload");
    });
    expect(result.current.profilerTab).toBe("upload");
  });

  it("does not analyze without selected user", async () => {
    // Return empty user list
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ user_ids: [] }),
    });

    const { result } = renderHook(() => useProfiler());
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });

    const fetchCountBefore = mockFetch.mock.calls.length;
    await act(async () => {
      await result.current.analyzeTestUser();
    });

    // No additional fetch call should have been made
    expect(mockFetch.mock.calls.length).toBe(fetchCountBefore);
  });
});
