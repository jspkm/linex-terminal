import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLearnProfiles } from "@/app/hooks/useLearnProfiles";

const mockFetch = vi.fn();
global.fetch = mockFetch;

beforeEach(() => {
  mockFetch.mockReset();
});

describe("useLearnProfiles", () => {
  it("initializes with default state", () => {
    const { result } = renderHook(() => useLearnProfiles());
    expect(result.current.genLoading).toBe(false);
    expect(result.current.genError).toBe("");
    expect(result.current.learnInProgress).toBe(false);
    expect(result.current.learnK).toBe(10);
    expect(result.current.catalog).toBeNull();
    expect(result.current.catalogList).toEqual([]);
    expect(result.current.selectedCatalogVersion).toBe("");
    expect(result.current.uploadedDatasets).toEqual([]);
  });

  it("fetches catalog list", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        catalogs: [
          { version: "v_abc", k: 5, source: "test", profile_count: 5 },
          { version: "v_xyz", k: 10, source: "test", profile_count: 10 },
        ],
      }),
    });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchCatalogList();
    });

    expect(result.current.catalogList).toHaveLength(2);
  });

  it("auto-selects first catalog when none selected", async () => {
    mockFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          catalogs: [{ version: "v_first", k: 5, source: "test", profile_count: 5 }],
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ version: "v_first", profiles: [], k: 5 }),
      });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchCatalogList();
    });

    expect(result.current.selectedCatalogVersion).toBe("v_first");
  });

  it("clears catalog when list is empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ catalogs: [] }),
    });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchCatalogList();
    });

    expect(result.current.selectedCatalogVersion).toBe("");
    expect(result.current.catalog).toBeNull();
  });

  it("loads a specific catalog", async () => {
    const mockCatalog = {
      version: "v_test",
      k: 5,
      profiles: [{ profile_id: "P0", ltv: 100 }],
      total_learning_population: 1000,
    };
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockCatalog),
    });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.loadCatalog("v_test");
    });

    expect(result.current.catalog?.version).toBe("v_test");
    expect(result.current.selectedCatalogVersion).toBe("v_test");
  });

  it("fetches uploaded datasets", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        datasets: [
          { dataset_id: "ds_1", upload_name: "Portfolio A", row_count: 5000 },
        ],
      }),
    });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchUploadedDatasets();
    });

    expect(result.current.uploadedDatasets).toHaveLength(1);
    expect(result.current.uploadedDatasets[0].upload_name).toBe("Portfolio A");
  });

  it("sets learnK", () => {
    const { result } = renderHook(() => useLearnProfiles());
    act(() => {
      result.current.setLearnK(15);
    });
    expect(result.current.learnK).toBe(15);
  });

  it("exposes setLearnSource", () => {
    const { result } = renderHook(() => useLearnProfiles());
    // setLearnSource triggers a useEffect that may auto-initialize, so just verify it exists
    expect(typeof result.current.setLearnSource).toBe("function");
  });

  it("handles failed catalog fetch gracefully", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchCatalogList();
    });

    // Should not throw, just leave state unchanged
    expect(result.current.catalogList).toEqual([]);
  });

  it("handles network error on catalog fetch", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useLearnProfiles());
    await act(async () => {
      await result.current.fetchCatalogList();
    });

    expect(result.current.catalogList).toEqual([]);
  });
});
