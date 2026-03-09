"use client";

import { useState, useEffect, useCallback, useMemo, Fragment, useRef } from "react";
import Papa from "papaparse";
import { Upload, FileText, Search, Activity, Loader2, Users, PanelLeft, Boxes, ChevronDown, ChevronRight, Square, Trash2, ArrowUp } from "lucide-react";
import { cn } from "@/lib/utils";

const CLOUD_FUNCTION_URL = process.env.NODE_ENV === "development"
  ? "http://127.0.0.1:5050/linexonewhitelabeler/us-central1"
  : "/api";

// FR-2A: Behavioral axes — mirrors backend CORE_AXES
const BEHAVIORAL_AXES: { axis: string; label: string; features: string[] }[] = [
  { axis: "activity_recency", label: "Activity Recency", features: ["recency_days", "active_months", "temporal_spread"] },
  { axis: "purchase_frequency", label: "Purchase Frequency", features: ["frequency_per_month", "transaction_count", "cadence_mean", "cadence_std"] },
  { axis: "spend_intensity", label: "Spend Intensity", features: ["total_spend", "avg_order_value", "max_order_value", "unique_products", "product_diversity"] },
  { axis: "refund_return", label: "Refund / Return", features: ["cancellation_rate", "cancellation_count"] },
];
const PRIMARY_FEATURES = new Set(BEHAVIORAL_AXES.map(a => a.features[0]));

type View = "profiler" | "generator";
type ProfilerTab = "test" | "upload";
type GeneratorTab = "train" | "catalog" | "experiment";

export default function Home() {
  const [activeView, setActiveView] = useState<View>("profiler");
  const [profilerTab, setProfilerTab] = useState<ProfilerTab>("test");
  const [generatorTab, setGeneratorTab] = useState<GeneratorTab>("train");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  // Test Users State
  const [testUserIds, setTestUserIds] = useState<string[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [testUsersLoading, setTestUsersLoading] = useState(false);

  // Upload State
  const [file, setFile] = useState<File | null>(null);
  const [customerId, setCustomerId] = useState("uploaded");

  // Common State
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [results, setResults] = useState<any>(null);
  const [error, setError] = useState("");

  // Profile Generator State
  const [genLoading, setGenLoading] = useState(false);
  const [genError, setGenError] = useState("");
  const [trainStatus, setTrainStatus] = useState("");
  const [trainSource, setTrainSource] = useState("uploaded");
  const [trainUploadFile, setTrainUploadFile] = useState<File | null>(null);
  const [trainUploadName, setTrainUploadName] = useState("");
  const [trainUploadSubmitted, setTrainUploadSubmitted] = useState(false);
  const [pendingUploadedPortfolioName, setPendingUploadedPortfolioName] = useState("");
  const [uploadedDatasets, setUploadedDatasets] = useState<any[]>([]);
  const [trainSourceAutoInitialized, setTrainSourceAutoInitialized] = useState(false);
  const [trainK, setTrainK] = useState(10);
  const [catalog, setCatalog] = useState<any>(null);
  const [catalogList, setCatalogList] = useState<any[]>([]);
  const [selectedCatalogVersion, setSelectedCatalogVersion] = useState("");
  const [expandedProfile, setExpandedProfile] = useState<string | null>(null);

  // Experiment State
  const [experimentId, setExperimentId] = useState<string | null>(null);
  const [experimentState, setExperimentState] = useState<any>(null);
  const [experimentPolling, setExperimentPolling] = useState(false);
  const [experimentStarting, setExperimentStarting] = useState(false);
  const [savedExperiments, setSavedExperiments] = useState<any[]>([]);
  const [selectedSavedExperimentId, setSelectedSavedExperimentId] = useState<string | null>(null);
  const [showExperimentProgress, setShowExperimentProgress] = useState(false);

  // Incentive Set State
  const [incentiveSets, setIncentiveSets] = useState<any[]>([]);
  const [selectedIncentiveSetVersion, setSelectedIncentiveSetVersion] = useState("");
  const profilerAbortRef = useRef<AbortController | null>(null);
  const learnXhrRef = useRef<XMLHttpRequest | null>(null);
  const learnFetchAbortRef = useRef<AbortController | null>(null);
  const activeLearnUploadNameRef = useRef("");
  const activeLearnStartedAtRef = useRef("");
  const learnStopRequestedRef = useRef(false);
  const experimentStartAbortRef = useRef<AbortController | null>(null);
  const KMEANS_STATUS_DETAILS = [
    "Step 1: Standardizing behavior features so dimensions are comparable.",
    "Step 2: Initializing K centroids in feature space.",
    "Step 3: Assigning each portfolio to its nearest centroid.",
    "Step 4: Recomputing centroids from assigned members.",
    "Step 5: Repeating assign/recompute until clusters stabilize.",
    "Distance metric: Euclidean distance on normalized features.",
    "Centroid meaning: average behavior vector for a profile group.",
    "Higher K creates more granular profiles with smaller groups.",
    "Lower K creates broader profiles with larger groups.",
    "Recency and cadence features influence activity-based separation.",
    "Spend intensity features shape value-tier separation.",
    "Refund/return features isolate cancellation-heavy behavior.",
    "Temporal spread helps separate bursty vs steady shoppers.",
    "Outlier clipping keeps extreme values from dominating clusters.",
    "Population share is computed from cluster membership counts.",
    "Profile labels are generated from learned centroid patterns.",
    "Portfolio LTV is aggregated from member-level profile economics.",
    "Final model stores centroids, dispersion, and scaling params.",
    "Catalog versioning preserves reproducibility for assignments.",
    "Post-train, portfolios are assignable to nearest learned profile.",
  ];

  // Load test user IDs on mount
  useEffect(() => {
    fetchTestUsers();
  }, []);

  const fetchTestUsers = async () => {
    setTestUsersLoading(true);
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_test_users`);
      if (res.ok) {
        const data = await res.json();
        setTestUserIds(data.user_ids || []);
        if (data.user_ids?.length > 0) {
          setSelectedUserId(data.user_ids[0]);
        }
      }
    } catch {
      // Silently fail — test users may not be available
    } finally {
      setTestUsersLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const analyzeTestUser = async () => {
    if (!selectedUserId) return;
    const controller = new AbortController();
    profilerAbortRef.current = controller;
    setLoading(true);
    setLoadingStep("Profiling with Gemini...");
    setError("");
    setResults(null);
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/analyze_test_user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: selectedUserId }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Failed to analyze test user");
      }
      setLoadingStep("Matching credit cards...");
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setError(err.message || "An error occurred");
      }
    } finally {
      setLoading(false);
      setLoadingStep("");
      profilerAbortRef.current = null;
    }
  };

  const processFile = async () => {
    if (!file) return;
    const controller = new AbortController();
    profilerAbortRef.current = controller;

    setLoading(true);
    setError("");

    try {
      const text = await file.text();
      const parsed = Papa.parse(text, { header: true, skipEmptyLines: true });
      const transactions = parsed.data;

      const res = await fetch(`${CLOUD_FUNCTION_URL}/analyze_transactions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transactions, customer_id: customerId }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error("Failed to analyze transactions");
      const data = await res.json();
      setResults(data);
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setError(err.message || "An error occurred");
      }
    } finally {
      setLoading(false);
      profilerAbortRef.current = null;
    }
  };

  const stopProfilerProcess = () => {
    if (profilerAbortRef.current) {
      profilerAbortRef.current.abort();
      profilerAbortRef.current = null;
    }
    setLoading(false);
    setLoadingStep("");
    setResults(null);
    setError("");
  };

  const postJsonWithUploadProgress = (
    url: string,
    body: any,
    onProgress: (pct: number) => void,
    onUploadComplete: () => void,
    timeoutMs = 180000,
  ) => {
    return new Promise<any>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      learnXhrRef.current = xhr;
      xhr.open("POST", url, true);
      xhr.setRequestHeader("Content-Type", "application/json");
      xhr.timeout = timeoutMs;

      xhr.upload.onprogress = (evt) => {
        if (!evt.lengthComputable) return;
        const pct = Math.max(0, Math.min(100, Math.round((evt.loaded / evt.total) * 100)));
        onProgress(pct);
      };
      xhr.upload.onload = () => onUploadComplete();
      xhr.ontimeout = () => {
        learnXhrRef.current = null;
        reject(new Error("Training request timed out after 3 minutes. Try a smaller file."));
      };
      xhr.onerror = () => {
        learnXhrRef.current = null;
        reject(new Error("Network error during upload"));
      };
      xhr.onload = () => {
        learnXhrRef.current = null;
        const raw = xhr.responseText || "";
        let data: any = {};
        try { data = raw ? JSON.parse(raw) : {}; } catch { /* ignore */ }
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(data);
        } else {
          reject(new Error(data.error || "Training failed"));
        }
      };

      xhr.send(JSON.stringify(body));
    });
  };

  const startBackendElapsedStatus = (label: string, details: string[] = []) => {
    const started = Date.now();
    let tickCount = 0;
    const tick = () => {
      const secs = Math.max(0, Math.floor((Date.now() - started) / 1000));
      let text = label;
      if (details.length > 0) {
        if (tickCount === 0) {
          text = label;
        } else {
          text = details[(tickCount - 1) % details.length];
        }
      }
      setTrainStatus(`${text} (${secs}s elapsed)`);
    };
    tick();
    const timer = setInterval(() => {
      tickCount += 1;
      tick();
    }, 2200);
    return () => clearInterval(timer);
  };

  // ---- Profile Generator handlers ----
  const trainProfiles = async () => {
    learnStopRequestedRef.current = false;
    setGenLoading(true);
    setGenError("");
    setTrainStatus("Starting...");
    let stopElapsedStatus: (() => void) | null = null;
    activeLearnStartedAtRef.current = new Date().toISOString();
    try {
      let body: any = { source: trainSource, k: trainK };
      let currentUploadName = "";

      if (trainSource === "uploaded") {
        setTrainStatus("Preparing upload...");
        if (!trainUploadFile) {
          throw new Error("Upload a transaction CSV file to train profiles");
        }
        currentUploadName = trainUploadName.trim();
        activeLearnUploadNameRef.current = currentUploadName;
        if (!currentUploadName) {
          throw new Error("Enter a name for this upload");
        }

        const csvText = await trainUploadFile.text();
        if (!csvText.trim()) {
          throw new Error("Upload file is empty");
        }
        setTrainUploadSubmitted(true);
        body = {
          source: "uploaded",
          k: trainK,
          upload_name: currentUploadName,
          csv_text: csvText,
        };
        setTrainStatus("Uploading... 0%");
      } else {
        setTrainStatus("Training...");
      }

      let data: any;
      if (trainSource === "uploaded") {
        data = await postJsonWithUploadProgress(
          `${CLOUD_FUNCTION_URL}/learn_profiles`,
          body,
          (pct) => setTrainStatus(`Uploading... ${pct}%`),
          () => {
            setPendingUploadedPortfolioName(currentUploadName);
            setTrainSource("uploaded-pending");
            setTrainStatus("Upload complete. Starting K-Means clustering...");
            stopElapsedStatus = startBackendElapsedStatus(
              "Learning profiles with K-Means clustering.",
              KMEANS_STATUS_DETAILS,
            );
          },
          180000,
        );
      } else {
        setTrainStatus("Submitting learn request...");
        stopElapsedStatus = startBackendElapsedStatus(
          "Learning profiles with K-Means clustering.",
          KMEANS_STATUS_DETAILS,
        );
        const controller = new AbortController();
        learnFetchAbortRef.current = controller;
        const timeoutId = setTimeout(() => controller.abort(), 180000);
        let res: Response;
        try {
          res = await fetch(`${CLOUD_FUNCTION_URL}/learn_profiles`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
            signal: controller.signal,
          });
        } finally {
          clearTimeout(timeoutId);
          learnFetchAbortRef.current = null;
        }
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || "Training failed");
        }
        data = await res.json();
      }
      setCatalog(data);
      if (data?.upload_dataset_id) {
        setPendingUploadedPortfolioName("");
        setTrainSource(`uploaded-dataset:${data.upload_dataset_id}`);
      }
      if (stopElapsedStatus) {
        stopElapsedStatus();
        stopElapsedStatus = null;
      }
      setTrainStatus("Learn complete.");
      setSelectedCatalogVersion(data.version);
      setGeneratorTab("catalog");
      fetchCatalogList();
      fetchUploadedDatasets();
    } catch (err: any) {
      if (learnStopRequestedRef.current) {
        setGenError("");
      } else if (err?.name === "AbortError") {
        setGenError("Training request timed out after 3 minutes. Try a smaller file.");
      } else {
        setGenError(err.message || "Training failed");
      }
    } finally {
      if (stopElapsedStatus) stopElapsedStatus();
      learnXhrRef.current = null;
      learnFetchAbortRef.current = null;
      activeLearnUploadNameRef.current = "";
      activeLearnStartedAtRef.current = "";
      learnStopRequestedRef.current = false;
      setGenLoading(false);
      setTrainStatus("");
      setTrainUploadSubmitted(false);
    }
  };

  const cleanupStoppedLearnData = async () => {
    const uploadName = activeLearnUploadNameRef.current.trim();
    const startedAt = activeLearnStartedAtRef.current;
    if (!uploadName || !startedAt) return;

    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_uploaded_training_datasets`);
      if (!res.ok) return;
      const data = await res.json();
      const datasets = data.datasets || [];
      const startedMs = Date.parse(startedAt);
      const candidates = datasets.filter((d: any) => {
        const sameName = String(d.upload_name || "").trim() === uploadName;
        const createdMs = Date.parse(String(d.created_at || ""));
        return sameName && Number.isFinite(createdMs) && createdMs >= (startedMs - 10000);
      });
      for (const d of candidates) {
        await fetch(`${CLOUD_FUNCTION_URL}/delete_portfolio_dataset/${d.dataset_id}`, { method: "DELETE" });
      }
      await fetchUploadedDatasets();
      await fetchCatalogList();
    } catch {
      // best-effort cleanup only
    }
  };

  const stopLearnProcess = async () => {
    learnStopRequestedRef.current = true;
    if (learnXhrRef.current) {
      learnXhrRef.current.abort();
      learnXhrRef.current = null;
    }
    if (learnFetchAbortRef.current) {
      learnFetchAbortRef.current.abort();
      learnFetchAbortRef.current = null;
    }
    await cleanupStoppedLearnData();
    setGenLoading(false);
    setTrainStatus("");
    setTrainUploadSubmitted(false);
    setPendingUploadedPortfolioName("");
    setTrainSource("uploaded");
  };

  const deleteSelectedPortfolio = async () => {
    if (!trainSource.startsWith("uploaded-dataset:")) return;
    const datasetId = trainSource.split(":", 2)[1] || "";
    if (!datasetId) return;

    const ok = window.confirm("Delete this portfolio and all associated learned catalogs/experiments?");
    if (!ok) return;

    setGenLoading(true);
    setGenError("");
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/delete_portfolio_dataset/${datasetId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Failed to delete portfolio dataset");
      }

      const listRes = await fetch(`${CLOUD_FUNCTION_URL}/list_uploaded_training_datasets`);
      if (listRes.ok) {
        const data = await listRes.json();
        const datasets = data.datasets || [];
        setUploadedDatasets(datasets);
        if (datasets.length > 0) {
          setTrainSource(`uploaded-dataset:${datasets[0].dataset_id}`);
        } else {
          setTrainSource("uploaded");
        }
      } else {
        setTrainSource("uploaded");
      }

      fetchCatalogList();
    } catch (err: any) {
      setGenError(err.message || "Failed to delete portfolio dataset");
    } finally {
      setGenLoading(false);
    }
  };

  const fetchCatalogList = async () => {
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_profile_catalogs`);
      if (res.ok) {
        const data = await res.json();
        const catalogs = data.catalogs || [];
        setCatalogList(catalogs);
        // Default to latest catalog if nothing selected yet
        if (!selectedCatalogVersion && catalogs.length > 0) {
          setSelectedCatalogVersion(catalogs[0].version);
          loadCatalog(catalogs[0].version);
        }
      }
    } catch { /* silent */ }
  };

  const fetchUploadedDatasets = async () => {
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_uploaded_training_datasets`);
      if (res.ok) {
        const data = await res.json();
        setUploadedDatasets(data.datasets || []);
      } else {
        const errData = await res.json().catch(() => ({}));
        setGenError(errData.error || "Failed to load uploaded datasets. Redeploy backend/hosting rewrites if this endpoint is missing.");
      }
    } catch {
      setGenError("Failed to load uploaded datasets. Check backend availability.");
    }
  };

  const loadCatalog = async (version?: string) => {
    setGenLoading(true);
    try {
      const url = version
        ? `${CLOUD_FUNCTION_URL}/profile_catalog/${version}`
        : `${CLOUD_FUNCTION_URL}/profile_catalog`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setCatalog(data);
        setSelectedCatalogVersion(data.version);
      }
    } catch { /* silent */ }
    finally { setGenLoading(false); }
  };

  // Load catalog list when switching to generator view
  useEffect(() => {
    if (activeView === "generator") {
      fetchCatalogList();
      fetchUploadedDatasets();
    }
  }, [activeView]);

  // Default to Upload source when no uploaded datasets are available
  useEffect(() => {
    if (!trainUploadFile && uploadedDatasets.length === 0 && trainSource !== "uploaded" && trainSource !== "uploaded-pending") {
      setTrainSource("uploaded");
    }
  }, [trainUploadFile, uploadedDatasets, trainSource]);

  // When datasets exist, default to the latest one unless a valid saved dataset is already selected
  useEffect(() => {
    if (uploadedDatasets.length === 0) return;
    const firstDatasetId = String(uploadedDatasets[0]?.dataset_id || "");
    if (!firstDatasetId) return;

    if (trainSource === "uploaded" && !trainSourceAutoInitialized && !trainUploadFile) {
      setTrainSource(`uploaded-dataset:${firstDatasetId}`);
      setTrainSourceAutoInitialized(true);
      return;
    }

    if (trainSource.startsWith("uploaded-dataset:")) {
      const selectedId = trainSource.split(":", 2)[1] || "";
      const exists = uploadedDatasets.some((d: any) => d.dataset_id === selectedId);
      if (!exists) {
        setTrainSource(`uploaded-dataset:${firstDatasetId}`);
      }
    }
  }, [uploadedDatasets, trainSource, trainSourceAutoInitialized, trainUploadFile]);

  // Load a catalog when switching to Catalog/Optimize tab:
  // - If a version is already selected, reload that version (preserves selection across tabs)
  // - Otherwise, load the latest catalog
  useEffect(() => {
    if (activeView === "generator" && (generatorTab === "catalog" || generatorTab === "experiment")) {
      loadCatalog(selectedCatalogVersion || undefined);
    }
    if (activeView === "generator" && generatorTab === "experiment") {
      fetchIncentiveSets();
      if (selectedCatalogVersion) {
        fetchSavedExperiments(selectedCatalogVersion);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeView, generatorTab]);

  // Optimize polling logic
  useEffect(() => {
    if (!experimentId || !experimentPolling) return;

    const poll = async () => {
      try {
        const res = await fetch(`${CLOUD_FUNCTION_URL}/optimize_status/${experimentId}`);
        if (res.ok) {
          const data = await res.json();
          setExperimentState(data);

          if (data.status === "completed" || data.status === "failed" || data.status === "cancelled") {
            setExperimentPolling(false);
            // Auto-save on completion or cancellation (with partial results)
            if (data.status === "completed" || data.status === "cancelled") {
              fetch(`${CLOUD_FUNCTION_URL}/save_optimize/${experimentId}`, { method: "POST" })
                .then(() => fetchSavedExperiments(selectedCatalogVersion || undefined))
                .catch(() => { });
            }
          }
        }
      } catch {
        // silently fail on poll
      }
    };

    poll(); // Initial poll
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [experimentId, experimentPolling]);

  const startExperiment = async () => {
    if (!selectedCatalogVersion) return;

    const controller = new AbortController();
    experimentStartAbortRef.current = controller;
    setGenLoading(true);
    setExperimentStarting(true);
    setGenError("");
    setExperimentState(null);
    setExperimentId(null);
    setShowExperimentProgress(true);

    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/start_optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          catalog_version: selectedCatalogVersion,
          incentive_set_version: selectedIncentiveSetVersion || undefined,
        }),
        signal: controller.signal,
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || "Failed to start optimization");
      }
      const data = await res.json();
      setExperimentId(data.experiment_id);
      setExperimentPolling(true);
    } catch (err: any) {
      if (err?.name !== "AbortError") {
        setGenError(err.message || "Failed to start optimization");
      }
    } finally {
      experimentStartAbortRef.current = null;
      setExperimentStarting(false);
      setGenLoading(false);
    }
  };

  const stopExperiment = async () => {
    if (experimentStartAbortRef.current) {
      experimentStartAbortRef.current.abort();
      experimentStartAbortRef.current = null;
    }
    if (!experimentId) {
      setExperimentStarting(false);
      setGenLoading(false);
      setShowExperimentProgress(false);
      return;
    }
    try {
      await fetch(`${CLOUD_FUNCTION_URL}/cancel_optimize/${experimentId}`, { method: "POST" });
      await fetch(`${CLOUD_FUNCTION_URL}/delete_optimize/${experimentId}`, { method: "DELETE" });
    } catch {
      // silently fail
    } finally {
      setExperimentPolling(false);
      setExperimentState(null);
      setExperimentId(null);
      setSelectedSavedExperimentId(null);
      fetchSavedExperiments(selectedCatalogVersion || undefined);
      setExperimentStarting(false);
      setGenLoading(false);
    }
  };

  const saveExperiment = async () => {
    if (!experimentId) return;
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/save_optimize/${experimentId}`, { method: "POST" });
      if (res.ok) {
        setGenError("");
      }
    } catch {
      setGenError("Failed to save optimization");
    }
  };

  const deleteExperiment = async () => {
    if (!experimentId) return;
    try {
      await fetch(`${CLOUD_FUNCTION_URL}/delete_optimize/${experimentId}`, { method: "DELETE" });
      setExperimentState(null);
      setExperimentId(null);
      setSelectedSavedExperimentId(null);
      fetchSavedExperiments(selectedCatalogVersion || undefined);
    } catch {
      setGenError("Failed to delete optimization");
    }
  };

  const fetchSavedExperiments = async (catalogVersion?: string) => {
    try {
      const url = catalogVersion
        ? `${CLOUD_FUNCTION_URL}/list_optimizations?catalog_version=${catalogVersion}`
        : `${CLOUD_FUNCTION_URL}/list_optimizations`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        const exps = data.experiments || [];
        setSavedExperiments(exps);
        // Auto-select the latest saved experiment
        if (exps.length > 0) {
          loadSavedExperiment(exps[0].experiment_id);
        } else {
          setSelectedSavedExperimentId(null);
          setExperimentState(null);
          setExperimentId(null);
        }
      }
    } catch { /* silent */ }
  };

  const fetchIncentiveSets = async () => {
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/list_incentive_sets`);
      if (res.ok) {
        const data = await res.json();
        const sets = data.incentive_sets || [];
        setIncentiveSets(sets);
        // Auto-select the default, or the first one
        const defaultSet = sets.find((s: any) => s.is_default);
        if (defaultSet) {
          setSelectedIncentiveSetVersion(defaultSet.version);
        } else if (sets.length > 0 && !selectedIncentiveSetVersion) {
          setSelectedIncentiveSetVersion(sets[0].version);
        }
      }
    } catch { /* silent */ }
  };

  const loadSavedExperiment = async (expId: string) => {
    setSelectedSavedExperimentId(expId);
    // Only clear progress when switching to a different experiment
    if (expId !== experimentId) {
      setShowExperimentProgress(false);
    }
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/load_optimize/${expId}`);
      if (res.ok) {
        const data = await res.json();
        setExperimentState(data);
        setExperimentId(expId);
      }
    } catch { /* silent */ }
  };

  const deleteCatalog = async (version: string) => {
    if (!confirm(`Delete catalog ${version}? This cannot be undone.`)) return;
    try {
      const res = await fetch(`${CLOUD_FUNCTION_URL}/delete_catalog/${version}`, { method: "DELETE" });
      if (res.ok) {
        const newList = catalogList.filter((c: any) => c.version !== version);
        setCatalogList(newList);
        if (selectedCatalogVersion === version) {
          const next = newList.length > 0 ? newList[0].version : "";
          setSelectedCatalogVersion(next);
          if (next) loadCatalog(next); else setCatalog(null);
        }
      }
    } catch {
      setGenError("Failed to delete catalog");
    }
  };


  return (
    <div className="flex min-h-screen bg-[#F3F4F6]">
      {/* Sidebar */}
      <aside
        className={cn(
          "border-r border-[#E5E7EB] bg-[#F9FAFB] py-6 flex flex-col shrink-0 transition-[width] duration-300 ease-in-out overflow-hidden",
          isSidebarOpen ? "w-56 px-4" : "w-16 px-2 items-center"
        )}
      >
        <div className={cn("mb-8 flex items-center", isSidebarOpen ? "justify-between w-full pl-2" : "justify-center")}>
          {isSidebarOpen && <h1 className="text-2xl font-bold tracking-tight text-black whitespace-nowrap">linex qu</h1>}
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className={cn("p-1.5 text-slate-500 hover:bg-slate-200 rounded-md shrink-0", isSidebarOpen ? "-mr-2" : "")}
            title={isSidebarOpen ? "Close sidebar" : "Open sidebar"}
          >
            <PanelLeft className="h-5 w-5" />
          </button>
        </div>

        <nav className="space-y-1 w-full">
          <button
            onClick={() => setActiveView("profiler")}
            className={cn(
              "flex w-full items-center rounded-md py-2 text-sm font-medium transition-colors",
              isSidebarOpen ? "px-3 gap-3 justify-start" : "px-0 justify-center",
              activeView === "profiler"
                ? "bg-slate-200 text-slate-900"
                : "text-slate-600 hover:bg-slate-100"
            )}
            title={!isSidebarOpen ? "User Profiler" : undefined}
          >
            <Activity className="h-5 w-5 shrink-0" />
            {isSidebarOpen && <span className="whitespace-nowrap">User Profiler</span>}
          </button>
          <button
            onClick={() => setActiveView("generator")}
            className={cn(
              "flex w-full items-center rounded-md py-2 text-sm font-medium transition-colors",
              isSidebarOpen ? "px-3 gap-3 justify-start" : "px-0 justify-center",
              activeView === "generator"
                ? "bg-slate-200 text-slate-900"
                : "text-slate-600 hover:bg-slate-100"
            )}
            title={!isSidebarOpen ? "Profile Generator" : undefined}
          >
            <Boxes className="h-5 w-5 shrink-0" />
            {isSidebarOpen && <span className="whitespace-nowrap">Profile Generator</span>}
          </button>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 transition-all duration-300 ease-in-out">
        <div className="flex-1 p-8">
          <div className="mx-auto max-w-6xl space-y-8">
            {error && (
              <div className="rounded-md bg-red-50 p-4 text-red-700 border border-red-200">
                {error}
              </div>
            )}

            {activeView === "profiler" ? (
              <div className="space-y-8">

                <div className="rounded-xl border border-[#E5E7EB] bg-white shadow-sm flex flex-col min-h-[260px]">
                  {/* Tabs Header */}
                  <div className="flex border-b border-[#E5E7EB] px-2 pt-2">
                    <button
                      onClick={() => setProfilerTab("test")}
                      className={cn(
                        "px-6 py-3 text-sm border-b-2 -mb-px transition-colors flex items-center gap-2",
                        profilerTab === "test"
                          ? "border-black text-black font-bold"
                          : "font-medium border-transparent text-slate-500 hover:text-slate-700"
                      )}
                    >
                      <Users className="h-4 w-4" />
                      Test Users
                    </button>
                    <button
                      onClick={() => setProfilerTab("upload")}
                      className={cn(
                        "px-6 py-3 text-sm border-b-2 -mb-px transition-colors flex items-center gap-2",
                        profilerTab === "upload"
                          ? "border-black text-black font-bold"
                          : "font-medium border-transparent text-slate-500 hover:text-slate-700"
                      )}
                    >
                      <Upload className="h-4 w-4" />
                      Upload CSV
                    </button>
                  </div>

                  {/* Tab Content */}
                  <div className="p-6 flex-1 flex flex-col">
                    {/* Test Users Tab */}
                    {profilerTab === "test" && (
                      <div className="flex-1 flex flex-col">
                        {testUsersLoading ? (
                          <div className="flex items-center gap-2 text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading test users...
                          </div>
                        ) : testUserIds.length === 0 ? (
                          <p className="text-sm text-red-500">No test users found. Check data/test-users/ directory.</p>
                        ) : (
                          <>
                            <div>
                              <select
                                value={selectedUserId}
                                onChange={(e) => setSelectedUserId(e.target.value)}
                                className="rounded-md border px-3 py-2 text-sm bg-white min-w-[200px]"
                              >
                                {testUserIds.map((id) => (
                                  <option key={id} value={id}>
                                    User {id}
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div className="mt-auto flex items-center gap-4 pt-4">
                              <button
                                onClick={loading ? stopProfilerProcess : analyzeTestUser}
                                disabled={!selectedUserId}
                                aria-label="Submit"
                                title={loading ? "Stop" : "Submit"}
                                className="rounded-full bg-black w-8 h-8 text-white hover:opacity-80 disabled:opacity-50 flex items-center justify-center shrink-0"
                              >
                                {loading
                                  ? <Square className="h-3.5 w-3.5" />
                                  : <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
                                }
                              </button>
                              {loading && <InlineAnalyzingIndicator />}
                            </div>
                          </>
                        )}
                      </div>
                    )}

                    {/* Upload CSV Tab */}
                    {profilerTab === "upload" && (
                      <div className="flex-1 flex flex-col">
                        <div className="flex items-center gap-6">
                          <label className="flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed border-slate-300 py-4 hover:border-blue-500 hover:bg-slate-50 transition-colors w-1/2 shrink-0">
                            <div className="text-center">
                              <Upload className="mx-auto h-5 w-5 text-slate-400 mb-1" />
                              <span className="text-sm text-slate-600">
                                Click or drag CSV here
                              </span>
                            </div>
                            <input
                              type="file"
                              accept=".csv"
                              className="hidden"
                              onChange={handleFileUpload}
                            />
                          </label>

                          {file && (
                            <div className="flex-1 text-sm font-semibold text-slate-700 truncate">
                              {file.name}
                            </div>
                          )}
                        </div>

                        <div className="mt-auto flex items-center gap-4 pt-4">
                          <button
                            onClick={loading ? stopProfilerProcess : () => processFile()}
                            disabled={!file}
                            aria-label="Submit"
                            title={loading ? "Stop" : "Submit"}
                            className="rounded-full bg-black w-8 h-8 text-white hover:opacity-80 disabled:opacity-50 flex items-center justify-center shrink-0"
                          >
                            {loading
                              ? <Square className="h-3.5 w-3.5" />
                              : <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
                            }
                          </button>
                          {loading && <InlineAnalyzingIndicator />}
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Results Dashboard */}
                {results && (
                  <div className="space-y-8">
                    {/* TOON Results Output */}
                    <div className="overflow-hidden px-2">
                      <pre className="text-sm text-slate-900 overflow-x-auto whitespace-pre-wrap">
                        {formatToon(results.profile, results.card_recommendations)}
                      </pre>
                    </div>

                    {/* Duplicate Profile Assignment UI */}
                    {results.assignment && (
                      <div className="px-2 pt-4 border-t border-slate-200">
                        <ProfileAssignmentView assignment={results.assignment} />
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : activeView === "generator" ? (
              <ProfileGeneratorView
                genLoading={genLoading}
                genError={genError}
                trainStatus={trainStatus}
                generatorTab={generatorTab}
                setGeneratorTab={setGeneratorTab}
                trainSource={trainSource}
                setTrainSource={setTrainSource}
                trainUploadName={trainUploadName}
                setTrainUploadName={setTrainUploadName}
                trainUploadFile={trainUploadFile}
                setTrainUploadFile={setTrainUploadFile}
                trainUploadSubmitted={trainUploadSubmitted}
                setTrainUploadSubmitted={setTrainUploadSubmitted}
                pendingUploadedPortfolioName={pendingUploadedPortfolioName}
                setPendingUploadedPortfolioName={setPendingUploadedPortfolioName}
                uploadedDatasets={uploadedDatasets}
                deleteSelectedPortfolio={deleteSelectedPortfolio}
                trainK={trainK}
                setTrainK={setTrainK}
                trainProfiles={trainProfiles}
                stopLearnProcess={stopLearnProcess}
                catalog={catalog}
                catalogList={catalogList}
                selectedCatalogVersion={selectedCatalogVersion}
                setSelectedCatalogVersion={setSelectedCatalogVersion}
                loadCatalog={loadCatalog}
                expandedProfile={expandedProfile}
                setExpandedProfile={setExpandedProfile}
                startExperiment={startExperiment}
                stopExperiment={stopExperiment}
                deleteExperiment={deleteExperiment}
                deleteCatalog={deleteCatalog}
                experimentState={experimentState}
                experimentStarting={experimentStarting}
                showExperimentProgress={showExperimentProgress}
                savedExperiments={savedExperiments}
                selectedSavedExperimentId={selectedSavedExperimentId}
                loadSavedExperiment={loadSavedExperiment}
                fetchSavedExperiments={fetchSavedExperiments}
                incentiveSets={incentiveSets}
                selectedIncentiveSetVersion={selectedIncentiveSetVersion}
                setSelectedIncentiveSetVersion={setSelectedIncentiveSetVersion}
              />
            ) : null}
          </div>
        </div>
      </main>
    </div>
  );
}

// ========================================================
// Profile Generator View
// ========================================================
function ProfileGeneratorView({
  genLoading, genError, trainStatus, generatorTab, setGeneratorTab,
  trainSource, setTrainSource, trainUploadName, setTrainUploadName, trainUploadFile, setTrainUploadFile, trainUploadSubmitted, setTrainUploadSubmitted, pendingUploadedPortfolioName, setPendingUploadedPortfolioName, uploadedDatasets, deleteSelectedPortfolio, trainK, setTrainK, trainProfiles, stopLearnProcess,
  catalog, catalogList, selectedCatalogVersion, setSelectedCatalogVersion, loadCatalog,
  expandedProfile, setExpandedProfile,
  startExperiment, stopExperiment, deleteExperiment, deleteCatalog,
  experimentState, experimentStarting, showExperimentProgress,
  savedExperiments, selectedSavedExperimentId, loadSavedExperiment, fetchSavedExperiments,
  incentiveSets, selectedIncentiveSetVersion, setSelectedIncentiveSetVersion,
}: any) {
  const [showAllIncentives, setShowAllIncentives] = useState(false);
  const onTrainFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const selected = e.target.files[0];
    setTrainUploadFile(selected);
    if (!trainUploadName.trim()) {
      const stripped = selected.name.replace(/\.[^/.]+$/, "");
      setTrainUploadName(stripped);
    }
  };
  const tabs: { key: string; label: string }[] = [
    { key: "train", label: "Learn" },
    { key: "catalog", label: "Catalog" },
    { key: "experiment", label: "Optimize" },
  ];

  return (
    <div className="space-y-6">
      {genError && (
        <div className="rounded-md bg-red-50 p-4 text-red-700 border border-red-200 text-sm">
          {genError}
        </div>
      )}

      <div className="rounded-xl border border-[#E5E7EB] bg-white shadow-sm">
        {/* Tab Bar */}
        <div className="flex border-b border-[#E5E7EB] px-2 pt-2 overflow-x-auto">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setGeneratorTab(t.key)}
              className={cn(
                "px-5 py-3 text-sm border-b-2 -mb-px transition-colors whitespace-nowrap",
                generatorTab === t.key
                  ? "border-black text-black font-bold"
                  : "font-medium border-transparent text-slate-500 hover:text-slate-700"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="p-6">
          {/* Training Panel */}
          {generatorTab === "train" && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Learn Profiles</h3>
                <p className="text-sm text-slate-500">Learn behavioral profiles from transaction data using K-Means clustering.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">Portfolio</label>
                  <div className="flex items-center gap-2">
                    <select
                      value={trainSource}
                      onChange={(e) => {
                        const next = e.target.value;
                        setTrainSource(next);
                        if (next !== "uploaded-pending") {
                          setPendingUploadedPortfolioName("");
                        }
                        if (next === "uploaded") {
                          setTrainUploadSubmitted(false);
                          setTrainUploadName("");
                        }
                      }}
                      className="rounded-md border px-3 py-2 text-sm bg-white w-full"
                    >
                      {uploadedDatasets.map((d: any) => (
                        <option key={d.dataset_id} value={`uploaded-dataset:${d.dataset_id}`}>
                          {d.upload_name || d.dataset_id} ({d.row_count || 0} rows)
                        </option>
                      ))}
                      {pendingUploadedPortfolioName && (
                        <option value="uploaded-pending">
                          {pendingUploadedPortfolioName}
                        </option>
                      )}
                      <option value="uploaded">Upload new portfolio</option>
                    </select>
                    {trainSource.startsWith("uploaded-dataset:") && (
                      <button
                        onClick={deleteSelectedPortfolio}
                        className="rounded-md border border-red-200 p-2 text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors"
                        title="Delete selected portfolio and associated data"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>

                  <div className="mt-4">
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Number of Profiles (K): <span className="font-bold text-black">{trainK}</span>
                    </label>
                    <input
                      type="range"
                      min={3}
                      max={15}
                      value={trainK}
                      onChange={(e) => setTrainK(parseInt(e.target.value))}
                      className="w-full accent-black"
                    />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>3</span>
                      <span>15</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-4">
                  {trainSource === "uploaded" && !trainUploadSubmitted && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Portfolio Name</label>
                        <input
                          type="text"
                          value={trainUploadName}
                          onChange={(e) => setTrainUploadName(e.target.value)}
                          className="rounded-md border px-3 py-2 text-sm bg-white w-full"
                          placeholder="e.g., Q1 2026 Retail Transactions"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-slate-700 mb-2">Transaction File</label>
                        <label className="flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed border-slate-300 py-4 hover:border-blue-500 hover:bg-slate-50 transition-colors">
                          <div className="text-center px-3">
                            <Upload className="mx-auto h-5 w-5 text-slate-400 mb-1" />
                            <span className="text-sm text-slate-600">Click or drag CSV here</span>
                          </div>
                          <input
                            type="file"
                            accept=".csv,text/csv"
                            className="hidden"
                            onChange={onTrainFileChange}
                          />
                        </label>
                        {trainUploadFile && (
                          <p className="mt-2 text-xs text-slate-500 truncate">{trainUploadFile.name}</p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4">
                <button
                  onClick={genLoading ? stopLearnProcess : trainProfiles}
                  aria-label="Submit"
                  title={genLoading ? "Stop" : "Submit"}
                  className="rounded-full bg-black w-8 h-8 text-white hover:opacity-80 disabled:opacity-50 flex items-center justify-center"
                >
                  {genLoading
                    ? <Square className="h-3.5 w-3.5" />
                    : <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
                  }
                </button>
                {genLoading && (
                  <span className="text-sm text-slate-600 flex items-center gap-2">
                    <img src="/linex-animated.svg" alt="Linex" className="h-5 w-5" />
                    <span>{trainStatus || "Working..."}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Catalog Panel */}
          {generatorTab === "catalog" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">Profile Catalog</h3>
                  <p className="text-sm text-slate-500">Canonical behavioral profiles learned from data.</p>
                </div>
                {catalogList.length > 0 && (
                  <div className="flex items-center gap-2">
                    <select
                      value={selectedCatalogVersion}
                      onChange={(e) => { setSelectedCatalogVersion(e.target.value); loadCatalog(e.target.value); }}
                      className="rounded-md border px-3 py-2 text-sm bg-white"
                    >
                      {catalogList.map((c: any) => (
                        <option key={c.version} value={c.version}>
                          {c.version} ({c.profile_count} profiles)
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => selectedCatalogVersion && deleteCatalog(selectedCatalogVersion)}
                      className="rounded-md border border-red-200 p-2 text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors"
                      title="Delete this catalog"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>

              {catalog ? (
                <div className="space-y-2">
                  <div className="text-xs text-slate-400 mb-3">
                    Version: <span className="font-mono">{catalog.version}</span> · Source: {catalog.source} · K={catalog.k}
                    {catalog.total_training_population > 0 && ` · ${catalog.total_training_population.toLocaleString()} users`}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 text-left text-slate-500">
                          <th className="py-2 pr-2 w-8"></th>
                          <th className="py-2 pr-4 font-medium">Profile</th>
                          <th className="py-2 pr-4 font-medium">Description</th>
                          <th className="py-2 pr-4 font-medium text-right">Portfolio LTV</th>
                          <th className="py-2 pr-4 font-medium text-right">Population</th>
                        </tr>
                      </thead>
                      <tbody>
                        {catalog.profiles.map((p: any) => (
                          <Fragment key={p.profile_id}>
                            <tr
                              className="border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors"
                              onClick={() => setExpandedProfile(expandedProfile === p.profile_id ? null : p.profile_id)}
                            >
                              <td className="py-2.5 pr-2 text-slate-400">
                                {expandedProfile === p.profile_id
                                  ? <ChevronDown className="h-4 w-4" />
                                  : <ChevronRight className="h-4 w-4" />
                                }
                              </td>
                              <td className="py-2.5 pr-4">
                                <div className="flex items-center gap-2.5">
                                  <span className={cn(
                                    "inline-flex items-center justify-center rounded-full text-white text-xs font-bold w-8 h-8 shrink-0",
                                    p.description?.toLowerCase().includes("return-heavy")
                                      ? "bg-amber-600"
                                      : "bg-slate-900"
                                  )}>
                                    {p.profile_id}
                                  </span>
                                  {p.label && (
                                    <span className="text-xs font-semibold text-slate-500">{p.label}</span>
                                  )}
                                </div>
                              </td>
                              <td className="py-2.5 pr-4 text-slate-700">{p.description}</td>
                              <td className="py-2.5 pr-4 text-right font-mono text-slate-600">
                                {p.portfolio_ltv != null ? `${p.portfolio_ltv < 0 ? '-' : ''}$${Math.abs(p.portfolio_ltv).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '—'}
                              </td>
                              <td className="py-2.5 pr-4 text-right font-mono text-slate-600">
                                {p.population_count > 0 ? p.population_count.toLocaleString() : ''}
                                <span className="text-slate-400 ml-1">({(p.population_share * 100).toFixed(1)}%)</span>
                              </td>
                            </tr>
                            {expandedProfile === p.profile_id && (
                              <tr key={`${p.profile_id}-detail`} className="bg-slate-50">
                                <td colSpan={5} className="p-4">
                                  <div className="grid grid-cols-2 gap-6">
                                    <div>
                                      <h4 className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">Centroid</h4>
                                      <div className="space-y-3">
                                        {BEHAVIORAL_AXES.map((ax) => {
                                          const primaryFeat = ax.features[0];
                                          const primaryVal = p.centroid[primaryFeat] ?? 0;
                                          const auxFeatures = ax.features.slice(1).filter(f => f in p.centroid);
                                          return (
                                            <div key={ax.axis}>
                                              <div className="flex items-center gap-2 text-xs mb-1">
                                                <span className="w-40 truncate text-slate-800 font-bold">{ax.label}</span>
                                                <div className="flex-1 bg-slate-200 rounded-full h-2 overflow-hidden">
                                                  <div className="bg-slate-900 h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(primaryVal * 10, 100))}%` }} />
                                                </div>
                                                <span className="font-mono text-slate-700 w-10 text-right font-semibold">{primaryVal.toFixed(2)}</span>
                                              </div>
                                              {auxFeatures.length > 0 && (
                                                <div className="space-y-0.5 pl-3">
                                                  {auxFeatures.map((feat) => {
                                                    const val = p.centroid[feat] ?? 0;
                                                    return (
                                                      <div key={feat} className="flex items-center gap-2 text-xs">
                                                        <span className="w-[148px] truncate text-slate-400">{feat}</span>
                                                        <div className="flex-1 bg-slate-100 rounded-full h-1.5 overflow-hidden">
                                                          <div className="bg-slate-400 h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(val * 10, 100))}%` }} />
                                                        </div>
                                                        <span className="font-mono text-slate-400 w-10 text-right">{val.toFixed(2)}</span>
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                    <div>
                                      <h4 className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">Dispersion (σ)</h4>
                                      <div className="space-y-3">
                                        {BEHAVIORAL_AXES.map((ax) => {
                                          const primaryFeat = ax.features[0];
                                          const primaryVal = p.dispersion[primaryFeat] ?? 0;
                                          const auxFeatures = ax.features.slice(1).filter(f => f in p.dispersion);
                                          return (
                                            <div key={ax.axis}>
                                              <div className="flex items-center gap-2 text-xs mb-1">
                                                <span className="w-40 truncate text-slate-800 font-bold">{ax.label}</span>
                                                <span className="font-mono text-slate-700 font-semibold">{primaryVal.toFixed(3)}</span>
                                              </div>
                                              {auxFeatures.length > 0 && (
                                                <div className="space-y-0.5 pl-3">
                                                  {auxFeatures.map((feat) => {
                                                    const val = p.dispersion[feat] ?? 0;
                                                    return (
                                                      <div key={feat} className="flex items-center gap-2 text-xs">
                                                        <span className="w-[148px] truncate text-slate-400">{feat}</span>
                                                        <span className="font-mono text-slate-400">{val.toFixed(3)}</span>
                                                      </div>
                                                    );
                                                  })}
                                                </div>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    </div>
                                  </div>
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        ))}
                        {/* Total Portfolio LTV Row */}
                        <tr className="bg-slate-50/50">
                          <td className="py-4 pr-2"></td>
                          <td className="py-4 pr-4" colSpan={2}>
                            <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Total Portfolio LTV</span>
                          </td>
                          <td className="py-4 pr-4 text-right font-mono text-slate-900 font-bold border-t border-slate-200">
                            {(() => {
                              const totalLTV = catalog.profiles.reduce((sum: number, p: any) => sum + (p.portfolio_ltv || 0), 0);
                              return `${totalLTV < 0 ? '-' : ''}$${Math.abs(totalLTV).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
                            })()}
                          </td>
                          <td className="py-4 pr-4"></td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-slate-500 py-8 text-center">
                  No catalog loaded. Train profiles first or select a saved catalog.
                </div>
              )}
            </div>
          )}

          {/* Optimize Panel */}
          {generatorTab === "experiment" && (
            <div className="space-y-6">
              <h3 className="text-lg font-semibold text-slate-900">Portfolio Optimization</h3>
              {catalogList.length > 0 && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-slate-500 shrink-0">Select profile:</label>
                  <select
                    value={selectedCatalogVersion}
                    onChange={(e) => { setSelectedCatalogVersion(e.target.value); loadCatalog(e.target.value); fetchSavedExperiments(e.target.value); }}
                    className="rounded-md border px-3 py-2 text-sm bg-white"
                  >
                    {catalogList.map((c: any) => (
                      <option key={c.version} value={c.version}>
                        {c.version} ({c.profile_count} profiles)
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() => selectedCatalogVersion && deleteCatalog(selectedCatalogVersion)}
                    className="rounded-md border border-red-200 p-2 text-red-500 hover:bg-red-50 hover:text-red-600 transition-colors"
                    title="Delete this catalog"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              )}

              {incentiveSets.length > 0 && (
                <div className="flex items-center gap-2">
                  <label className="text-sm text-slate-500 shrink-0">Incentive set:</label>
                  <select
                    value={selectedIncentiveSetVersion}
                    onChange={(e) => setSelectedIncentiveSetVersion(e.target.value)}
                    className="rounded-md border px-3 py-2 text-sm bg-white"
                  >
                    {incentiveSets.map((s: any) => (
                      <option key={s.version} value={s.version}>
                        {s.name || s.version} ({s.incentive_count} incentives){s.is_default ? " *" : ""}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {!catalog ? (
                <div className="text-sm text-slate-500 py-8 text-center">
                  No catalog loaded. Train profiles first or select a saved catalog.
                </div>
              ) : (
                <div className="space-y-6 border-t border-slate-200 pt-6">

                  <div className="flex items-center gap-3">
                    {(experimentState?.status === "running" || experimentStarting) ? (
                      <button
                        onClick={stopExperiment}
                        aria-label="Stop"
                        title="Stop"
                        className="rounded-full bg-black w-8 h-8 text-white hover:opacity-80 flex items-center justify-center"
                      >
                        <Square className="h-3.5 w-3.5" />
                      </button>
                    ) : (
                      <button
                        onClick={startExperiment}
                        disabled={genLoading}
                        aria-label="Submit"
                        title="Submit"
                        className="rounded-full bg-black w-8 h-8 text-white hover:opacity-80 disabled:opacity-50 flex items-center justify-center"
                      >
                        {genLoading
                          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          : <ArrowUp className="h-4 w-4" strokeWidth={2.25} />
                        }
                      </button>
                    )}
                    {experimentState && showExperimentProgress && (
                      <div className="min-w-0 flex-1 max-w-[520px]">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className={cn(
                            "px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider shrink-0",
                            experimentState.status === "running" ? "bg-blue-100 text-blue-700" :
                              experimentState.status === "completed" ? "bg-green-100 text-green-700" :
                                experimentState.status === "cancelled" ? "bg-amber-100 text-amber-700" :
                                  "bg-red-100 text-red-700"
                          )}>
                            {experimentState.status}
                          </span>
                          <div className="text-xs font-mono text-slate-500 shrink-0">{experimentState.progress}%</div>
                        </div>
                        <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full transition-all duration-500",
                              experimentState.status === "failed"
                                ? "bg-red-500"
                                : experimentState.status === "cancelled"
                                  ? "bg-amber-500"
                                  : "bg-blue-600"
                            )}
                            style={{ width: `${experimentState.progress}%` }}
                          />
                        </div>
                        <div className="text-xs text-slate-600 mt-1 truncate">
                          {experimentState.current_step}
                        </div>
                      </div>
                    )}
                  </div>

                  {savedExperiments.length > 1 && (
                    <div className="flex items-center gap-3">
                      <label className="text-xs font-medium text-slate-500 uppercase tracking-wider shrink-0">Saved Runs</label>
                      <select
                        value={selectedSavedExperimentId || ""}
                        onChange={(e) => {
                          if (e.target.value) loadSavedExperiment(e.target.value);
                        }}
                        className="rounded-md border px-3 py-1.5 text-sm bg-white flex-1"
                      >
                        {savedExperiments.map((exp: any) => (
                          <option key={exp.experiment_id} value={exp.experiment_id}>
                            {new Date(exp.completed_at || exp.started_at).toLocaleString()} — {exp.status} ({exp.result_count} profiles)
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {experimentState && (
                    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm space-y-6">
                      {experimentState.status === "failed" && (
                        <div className="rounded-md bg-red-50 p-4 text-red-700 text-sm">
                          Error: {experimentState.error}
                        </div>
                      )}

                      {experimentState.results && experimentState.results.length > 0 && (
                        <div className="mt-8 space-y-6">
                          {/* Results table — most important, shown first */}
                          <div>
                            <div className="flex items-center justify-between mb-4">
                              <h4 className="font-semibold text-slate-900">Optimal Incentive Programs</h4>
                              {(experimentState.status === "completed" || experimentState.status === "cancelled") && (
                                <button
                                  onClick={deleteExperiment}
                                  className="rounded-md border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-600 hover:bg-red-50 flex items-center gap-1.5"
                                >
                                  <Trash2 className="h-3.5 w-3.5" />
                                  Delete
                                </button>
                              )}
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b border-slate-200 text-left text-slate-500">
                                    <th className="py-2 pr-4 font-medium">Profile</th>
                                    <th className="py-2 pr-4 font-medium">Assigned Incentive(s)</th>
                                    <th className="py-2 pr-4 font-medium text-right">Orig LTV</th>
                                    <th className="py-2 pr-4 font-medium text-right">Gross LTV</th>
                                    <th className="py-2 pr-4 font-medium text-right">Cost</th>
                                    <th className="py-2 pr-4 font-medium text-right">Lift</th>
                                    <th className="py-2 pr-4 font-bold text-right">Final LTV</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {experimentState.results.map((r: any) => (
                                    <tr key={r.profile_id} className="border-b border-slate-100">
                                      <td className="py-3 pr-4 font-semibold text-slate-900">{r.profile_id}</td>
                                      <td className="py-3 pr-4 text-slate-700">
                                        <div className="flex flex-wrap gap-1">
                                          {(r.selected_incentives || []).map((inc: string, idx: number) => (
                                            <span key={idx} className="inline-flex bg-amber-100 text-amber-800 px-2 py-0.5 rounded text-xs font-semibold">
                                              {inc}
                                            </span>
                                          ))}
                                        </div>
                                      </td>
                                      <td className="py-3 pr-4 text-right font-mono text-slate-500">
                                        {`$${Math.round(r.original_portfolio_ltv).toLocaleString('en-US')}`}
                                      </td>
                                      <td className="py-3 pr-4 text-right font-mono text-slate-700">
                                        {`$${Math.round(r.new_gross_portfolio_ltv).toLocaleString('en-US')}`}
                                      </td>
                                      <td className="py-3 pr-4 text-right font-mono text-slate-700">
                                        {`-$${Math.round(r.portfolio_cost).toLocaleString('en-US')}`}
                                      </td>
                                      <td className="py-3 pr-4 text-right font-mono text-slate-700">
                                        {`+$${Math.round(r.lift).toLocaleString('en-US')}`}
                                      </td>
                                      <td className="py-3 pr-4 text-right font-mono text-slate-900 font-bold">
                                        {`$${Math.round(r.new_net_portfolio_ltv).toLocaleString('en-US')}`}
                                      </td>
                                    </tr>
                                  ))}
                                  <tr className="bg-slate-50/50">
                                    <td className="py-4 pr-4" colSpan={2}>
                                      <span className="text-[10px] uppercase tracking-wider text-slate-400 font-bold">Maximized Total Portfolio</span>
                                    </td>
                                    <td className="py-4 pr-4 text-right font-mono text-slate-900 font-bold border-t border-slate-200">
                                      {(() => {
                                        const totalOrig = experimentState.results.reduce((sum: number, r: any) => sum + (r.original_portfolio_ltv || 0), 0);
                                        return `$${Math.round(totalOrig).toLocaleString('en-US')}`;
                                      })()}
                                    </td>
                                    <td className="py-4 pr-4 text-right font-mono text-slate-700 border-t border-slate-200">
                                      {(() => {
                                        const totalGross = experimentState.results.reduce((sum: number, r: any) => sum + (r.new_gross_portfolio_ltv || 0), 0);
                                        return `$${Math.round(totalGross).toLocaleString('en-US')}`;
                                      })()}
                                    </td>
                                    <td className="py-4 pr-4 text-right font-mono text-slate-700 border-t border-slate-200">
                                      {(() => {
                                        const totalCost = experimentState.results.reduce((sum: number, r: any) => sum + (r.portfolio_cost || 0), 0);
                                        return `-$${Math.round(totalCost).toLocaleString('en-US')}`;
                                      })()}
                                    </td>
                                    <td className="py-4 pr-4 text-right font-mono text-slate-700 font-bold border-t border-slate-200">
                                      {(() => {
                                        const totalLift = experimentState.results.reduce((sum: number, r: any) => sum + (r.lift || 0), 0);
                                        return `+$${Math.round(totalLift).toLocaleString('en-US')}`;
                                      })()}
                                    </td>
                                    <td className="py-4 pr-4 text-right font-mono text-slate-900 font-bold border-t border-slate-200">
                                      {(() => {
                                        const totalNet = experimentState.results.reduce((sum: number, r: any) => sum + (r.new_net_portfolio_ltv || 0), 0);
                                        return `$${Math.round(totalNet).toLocaleString('en-US')}`;
                                      })()}
                                    </td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          </div>

                          {/* Methodology note — compact */}
                          <div className="text-xs text-slate-400 px-1">
                            Convergence-based optimization: each profile iterated until no improvement for {experimentState.iterations_per_profile} consecutive rounds. Only net-positive incentives retained (marginal LTV &gt; effective cost).
                          </div>

                          {/* Available Incentives — collapsed by default, at the bottom */}
                          {(() => {
                            const allIncentives = experimentState.available_incentives || [];
                            const PREVIEW_COUNT = 5;
                            const visibleIncentives = showAllIncentives ? allIncentives : allIncentives.slice(0, PREVIEW_COUNT);
                            const hiddenCount = allIncentives.length - PREVIEW_COUNT;
                            return (
                              <div className="rounded-lg border border-slate-200 bg-slate-50/50">
                                <button
                                  onClick={() => setShowAllIncentives(!showAllIncentives)}
                                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-100/50 transition-colors rounded-lg"
                                >
                                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                    Available Incentives ({allIncentives.length})
                                  </span>
                                  <ChevronDown className={cn("h-4 w-4 text-slate-400 transition-transform", showAllIncentives && "rotate-180")} />
                                </button>
                                <div className="px-4 pb-3">
                                  <div className="flex flex-wrap gap-1.5">
                                    {visibleIncentives.map((inc: any, idx: number) => (
                                      <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-white border border-slate-200 text-[11px] text-slate-500 font-medium">
                                        {inc.name}
                                        <span className="text-slate-300">${Math.round(inc.estimated_annual_cost_per_user * (inc.redemption_rate || 1))}</span>
                                      </span>
                                    ))}
                                    {!showAllIncentives && hiddenCount > 0 && (
                                      <span
                                        onClick={() => setShowAllIncentives(true)}
                                        className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-[11px] text-slate-400 font-medium cursor-pointer hover:bg-slate-200 transition-colors"
                                      >
                                        +{hiddenCount} more
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
// ========================================================
// Helpers
// ========================================================
const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884d8", "#82ca9d"];
const PROFILE_COLORS = [
  "#1e293b", "#334155", "#475569", "#64748b", "#94a3b8",
  "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6",
  "#ec4899", "#22c55e", "#a855f7", "#f97316", "#06b6d4",
];

function MetricCard({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded-xl border bg-white p-4 shadow-sm">
      <p className="text-xs font-medium text-slate-500 mb-1 leading-none">{title}</p>
      <p className="text-2xl font-bold tracking-tight text-slate-900">{value}</p>
    </div>
  );
}

function formatToon(profile: any, rec: any) {
  let profileToon = "linex_profile:\n profile:\n";
  if (profile.raw_toon) {
    profileToon = profile.raw_toon;
  } else if (profile.attributes) {
    for (const [key, attr] of Object.entries(profile.attributes)) {
      const a = attr as any;
      profileToon += `  ${key}: ${a.value} [${a.confidence}]\n`;
    }
  }

  let recToon = " card_recommendation:\n";
  if (rec.raw_toon) {
    recToon = rec.raw_toon.replace("linex_profile:\n", "");
  } else if (rec.recommendations) {
    const fields = "card_id,card_name,issuer,fit_score,match,estimated_annual_value,description";
    recToon += `  recommendations[${rec.recommendations.length}]{${fields}}:\n`;
    for (const r of rec.recommendations) {
      recToon += `   ${r.card_id},${r.card_name},${r.issuer},${r.fit_score},${r.why_it_matches},${r.estimated_annual_reward_value},${r.description}\n`;
    }
  }

  if (!profileToon.endsWith('\n')) profileToon += '\n';

  return profileToon + recToon;
}

const ALL_STATEMENTS = [
  "Brewing up something good...",
  "Let me dig into this...",
  "Hmm, let me see...",
  "One moment...",
  "Cooking up an answer...",
  "Poking around...",
  "Down the rabbit hole...",
  "Crunching the numbers...",
  "Dusting off the archives...",
  "Connecting the dots...",
  "Rummaging through my brain...",
  "Give me a sec...",
  "Chewing on this...",
  "Putting on my thinking cap...",
  "Let me work my magic...",
  "Diving in...",
  "Spinning up the gears...",
  "Cracking open the books...",
  "Hold my coffee...",
  "Summoning the answer...",
  "Untangling this...",
  "Sniffing out the details...",
  "Rolling up my sleeves...",
  "Consulting the oracle..."
];

function InlineAnalyzingIndicator() {
  const [stepIndex, setStepIndex] = useState(0);
  const [steps, setSteps] = useState<string[]>([]);

  useEffect(() => {
    // Shuffle and pick 10 random statements for this run
    const shuffled = [...ALL_STATEMENTS].sort(() => 0.5 - Math.random());
    setSteps(shuffled.slice(0, 10));
  }, []);

  useEffect(() => {
    if (steps.length === 0) return;
    const interval = setInterval(() => {
      setStepIndex((current) => (current + 1) % steps.length);
    }, 2200);
    return () => clearInterval(interval);
  }, [steps]);

  return (
    <div className="flex items-center gap-4 flex-1">
      <div className="relative flex items-center justify-center w-8 h-8 shrink-0">
        <div className="relative flex items-center justify-center w-full h-full">
          {/* Animated Linex Logo */}
          <img src="/linex-animated.svg" alt="Loading..." className="w-6 h-6" />
        </div>
      </div>
      <div className="h-5 overflow-hidden flex-1 relative">
        <div
          className="flex flex-col transition-transform duration-500 ease-in-out"
          style={{ transform: `translateY(-${stepIndex * 20}px)` }}
        >
          {steps.map((step, i) => (
            <div key={i} className="h-5 flex items-center text-sm font-medium text-slate-600">
              {step}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ========================================================
// Reusable Assignment View
// ========================================================
export function ProfileAssignmentView({ assignment }: { assignment: any }) {
  return (
    <div className="rounded-lg border border-slate-200 p-5 space-y-4">
      <div className="flex items-center gap-4">
        <span className="inline-flex items-center justify-center rounded-full bg-slate-900 text-white text-sm font-bold w-12 h-12">
          {assignment.profile_id}
        </span>
        <div>
          <div className="text-lg font-semibold text-slate-900">
            {assignment.profile_label || `Profile ${assignment.profile_id}`}
          </div>
          <div className="text-sm text-slate-500">
            Confidence: <span className="font-semibold text-slate-700">{(assignment.confidence * 100).toFixed(1)}%</span>
            {' · '}Customer: {assignment.customer_id}
          </div>
        </div>
      </div>

      {assignment.alternates && assignment.alternates.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Alternate Candidates</h4>
          <div className="flex gap-3">
            {assignment.alternates.map((alt: any, i: number) => (
              <div key={i} className="rounded-md border border-slate-200 px-3 py-2 text-sm">
                <span className="font-semibold">{alt.profile_id}</span>
                <span className="text-slate-400 ml-2">d={alt.distance}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {assignment.feature_vector && (
        <div>
          <h4 className="text-xs font-semibold text-slate-500 mb-3 uppercase tracking-wide">Feature Vector (normalized)</h4>
          <div className="grid grid-cols-2 gap-4">
            {BEHAVIORAL_AXES.map((ax) => {
              const primaryFeat = ax.features[0];
              const primaryVal = assignment.feature_vector[primaryFeat] ?? 0;
              const auxFeatures = ax.features.slice(1).filter((f: string) => f in assignment.feature_vector);
              return (
                <div key={ax.axis}>
                  <div className="flex items-center gap-2 text-xs mb-1">
                    <span className="w-40 truncate text-slate-800 font-bold">{ax.label}</span>
                    <div className="flex-1 bg-slate-200 rounded-full h-1.5 overflow-hidden">
                      <div className="bg-blue-600 h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(primaryVal * 10, 100))}%` }} />
                    </div>
                    <span className="font-mono text-slate-700 w-10 text-right font-semibold">{primaryVal.toFixed(2)}</span>
                  </div>
                  {auxFeatures.length > 0 && (
                    <div className="space-y-0.5 pl-3">
                      {auxFeatures.map((feat: string) => {
                        const val = assignment.feature_vector[feat] ?? 0;
                        return (
                          <div key={feat} className="flex items-center gap-2 text-xs">
                            <span className="w-[148px] truncate text-slate-400">{feat}</span>
                            <div className="flex-1 bg-slate-100 rounded-full h-1 overflow-hidden">
                              <div className="bg-blue-300 h-full rounded-full transition-all" style={{ width: `${Math.max(0, Math.min(val * 10, 100))}%` }} />
                            </div>
                            <span className="font-mono text-slate-400 w-10 text-right">{val.toFixed(2)}</span>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
