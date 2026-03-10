import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, model_validator
import json
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from config import GEMINI_API_KEY, MODEL
from models.profile_catalog import CanonicalProfile
from profile_generator.versioning import load_catalog
from profile_generator.incentive_manager import load_or_seed_default, get_incentive_cost_map
from profile_generator.firestore_client import (
    fs_save_optimization,
    fs_load_optimization,
    fs_list_optimizations,
    fs_delete_optimization,
    fs_load_incentive_set,
)
_gemini = None


def _get_gemini():
    """Lazy-init Gemini client on first use (avoids cold-start overhead)."""
    global _gemini
    if _gemini is None:
        try:
            from google import genai
            _gemini = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            pass
    return _gemini

# Global in-memory state for optimizations
_optimizations: Dict[str, "OptimizationState"] = {}
_deleted_optimization_ids: set[str] = set()


class ProfileIncentiveEvaluation(BaseModel):
    profile_id: str
    selected_incentives: List[str]
    gross_ltv: float
    estimated_cost: float
    net_ltv: float
    reasoning: str

class OptimizationResult(BaseModel):
    profile_id: str
    selected_incentives: List[str]
    original_portfolio_ltv: float
    new_gross_portfolio_ltv: float
    portfolio_cost: float
    new_net_portfolio_ltv: float
    lift: float
    reasoning: str

class OptimizationState(BaseModel):
    optimization_id: str
    catalog_version: str
    incentive_set_version: str = ""
    status: str  # "running", "completed", "failed", "cancelled"
    progress: int  # 0 to 100
    current_step: str
    iterations_per_profile: int
    available_incentives: List[Dict[str, Any]]
    results: List[OptimizationResult] = []
    error: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    cancelled: bool = False
    next_profile_index: int = 0
    max_iterations: int = 50
    patience: int = 3
    convergence_window: int = 6
    active_profile_id: str = ""
    active_profile_iteration: int = 0
    active_profile_no_improve: int = 0
    active_profile_best_net_ltv: float = float("-inf")
    active_profile_best_eval: Optional[Dict[str, Any]] = None
    active_profile_net_history: List[float] = []

    @model_validator(mode="before")
    @classmethod
    def _compat_legacy_id(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "optimization_id" not in data and "experiment_id" in data:
                data = dict(data)
                data["optimization_id"] = data.get("experiment_id")
        return data

def _strip_fences(raw: str) -> str:
    if not raw.startswith("```"):
        return raw
    lines = raw.split("\n")
    clean = []
    in_block = False
    for line in lines:
        if line.startswith("```") and not in_block:
            in_block = True
            continue
        if line.startswith("```") and in_block:
            break
        if in_block:
            clean.append(line)
    return "\n".join(clean)

def evaluate_incentive_bundle(
    profile: CanonicalProfile,
    incentives: list[dict],
    cost_map: dict[str, float],
) -> ProfileIncentiveEvaluation:
    """Ask LLM for optimal bundle with per-incentive marginal LTV, then
    programmatically keep only net-positive incentives."""
    gemini = _get_gemini()
    if not gemini:
        return ProfileIncentiveEvaluation(
            profile_id=profile.profile_id,
            selected_incentives=[],
            gross_ltv=profile.ltv,
            estimated_cost=0.0,
            net_ltv=profile.ltv,
            reasoning="No Gemini client"
        )

    system_prompt = (
        "You are an expert financial analyst optimizing credit card portfolio LTV. "
        "Given a canonical behavioral profile and available incentive programs, "
        "select the OPTIMAL BUNDLE that maximizes NET LTV (Gross LTV minus Total Cost). "
        "For EACH incentive you select, estimate its individual marginal_ltv — the "
        "incremental annual LTV it alone would add to the baseline — and estimate "
        "uptake_probability for this profile (0 to 1). "
        "Higher-spend profiles can have higher uptake for premium travel perks when fit is strong. "
        "Output ONLY a JSON object with this exact structure: {"
        "\"selected_incentives\": [{\"name\": \"<incentive_name>\", \"marginal_ltv\": <float>, \"uptake_probability\": <float>}, ...], "
        "\"gross_ltv\": <float>, "
        "\"estimated_cost\": <float>, "
        "\"net_ltv\": <float>, "
        "\"reasoning\": \"<string>\"}"
    )

    incentives_text = "\n".join(
        [f"- {inc['name']} (Effective Cost: ${round(inc['estimated_annual_cost_per_user'] * inc['redemption_rate'], 2)}/yr, redemption: {int(inc['redemption_rate']*100)}%)" for inc in incentives]
    )

    user_prompt = f"""
Profile Information:
ID: {profile.profile_id}
Label: {profile.label}
Description: {profile.description}
Baseline Per-User LTV: ${profile.ltv:.2f}

Behavioral Feature Centroid:
{json.dumps(profile.centroid, indent=2)}

Available Incentives:
{incentives_text}

Task:
1. Review the profile's spending behavior (recency, frequency, spend_intensity, refunds).
2. Select incentives that will drive enough incremental spend to exceed their cost.
3. For EACH selected incentive, estimate its marginal_ltv (the incremental LTV it adds).
4. For EACH selected incentive, estimate uptake_probability in [0, 1] for this profile.
5. Only include incentives where marginal_ltv > cost.
5. Gross LTV = Baseline + sum of all marginal_ltv values.
"""

    try:
        from google.genai import types
        # Bound per-profile model latency so one slow call cannot stall progress.
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                gemini.models.generate_content,
                model=MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                    response_mime_type="application/json",
                ),
            )
            response = future.result(timeout=35)

        raw_resp = _strip_fences(response.text.strip())
        data = json.loads(raw_resp)
        raw_selected = data.get("selected_incentives", [])
        reasoning = data.get("reasoning", "No reasoning provided.")
    except FuturesTimeoutError:
        return ProfileIncentiveEvaluation(
            profile_id=profile.profile_id,
            selected_incentives=[],
            gross_ltv=profile.ltv,
            estimated_cost=0.0,
            net_ltv=profile.ltv,
            reasoning="LLM timeout after 35s; kept baseline LTV with no incentives.",
        )
    except Exception as e:
        return ProfileIncentiveEvaluation(
            profile_id=profile.profile_id,
            selected_incentives=[],
            gross_ltv=profile.ltv,
            estimated_cost=0.0,
            net_ltv=profile.ltv,
            reasoning=f"LLM error: {e}",
        )

    # --- Programmatic filter: keep only net-positive incentives ---
    kept: list[str] = []
    kept_marginal_sum = 0.0
    kept_cost_sum = 0.0
    dropped: list[str] = []
    incentive_by_name = {str(inc.get("name", "")): inc for inc in incentives}

    def uptake_posterior(inc: dict) -> tuple[float, float]:
        prior_mean = max(0.0, min(1.0, float(inc.get("redemption_rate", 0.0))))
        prior_strength = max(1.0, float(inc.get("uptake_prior_strength", 20.0)))
        observed_successes = max(0.0, float(inc.get("uptake_observed_successes", 0)))
        observed_trials = max(observed_successes, float(inc.get("uptake_observed_trials", 0)))
        alpha = prior_mean * prior_strength + observed_successes
        beta = (1.0 - prior_mean) * prior_strength + (observed_trials - observed_successes)
        denom = alpha + beta
        if denom <= 0:
            return prior_mean, 0.0
        mean = alpha / denom
        variance = (alpha * beta) / (((denom ** 2) * (denom + 1.0)) or 1.0)
        std = math.sqrt(max(variance, 0.0))
        return max(0.0, min(1.0, mean)), std

    def blend_uptake(posterior_mean: float, posterior_std: float, llm_uptake: Optional[float]) -> tuple[float, float]:
        """Blend Bayesian prior/posterior with profile-specific LLM uptake signal.

        This is intentionally less conservative than a full lower-bound-only gate.
        """
        if llm_uptake is None:
            blended_mean = posterior_mean
        else:
            blended_mean = (0.65 * posterior_mean) + (0.35 * llm_uptake)
        blended_mean = max(0.0, min(1.0, blended_mean))
        blended_lcb = max(0.0, blended_mean - (0.5 * posterior_std))
        return blended_mean, blended_lcb

    for inc in raw_selected:
        # Handle both dict (with marginal_ltv) and plain string formats
        llm_uptake: Optional[float] = None
        if isinstance(inc, dict):
            name = inc.get("name", "")
            marginal = float(inc.get("marginal_ltv", 0.0))
            uptake_raw = inc.get("uptake_probability")
            if uptake_raw is not None:
                try:
                    llm_uptake = max(0.0, min(1.0, float(uptake_raw)))
                except Exception:
                    llm_uptake = None
        else:
            name = str(inc)
            marginal = 0.0

        inc_cfg = incentive_by_name.get(name, {})
        uptake_mean, uptake_std = uptake_posterior(inc_cfg)
        blended_uptake_mean, uptake_lcb = blend_uptake(uptake_mean, uptake_std, llm_uptake)
        cost = cost_map.get(name, 0.0)
        risk_adjusted_marginal = marginal * (uptake_lcb / blended_uptake_mean) if blended_uptake_mean > 1e-9 else 0.0

        # Slightly relaxed gate versus strict break-even to reduce over-conservatism.
        cost_gate = cost * 0.95
        if risk_adjusted_marginal > cost_gate:
            kept.append(name)
            kept_marginal_sum += risk_adjusted_marginal
            kept_cost_sum += cost
        else:
            dropped.append(
                f"{name} (adj marginal ${risk_adjusted_marginal:.2f} <= gate ${cost_gate:.2f}, uptake LCB {uptake_lcb:.2f})"
            )

    gross_ltv = profile.ltv + kept_marginal_sum
    net_ltv = gross_ltv - kept_cost_sum

    if dropped:
        reasoning += f" | Dropped net-negative: {'; '.join(dropped)}"

    return ProfileIncentiveEvaluation(
        profile_id=profile.profile_id,
        selected_incentives=kept,
        gross_ltv=round(gross_ltv, 2),
        estimated_cost=round(kept_cost_sum, 2),
        net_ltv=round(net_ltv, 2),
        reasoning=reasoning,
    )


def _enforce_baseline(
    evaluation: ProfileIncentiveEvaluation,
    baseline_ltv: float,
) -> ProfileIncentiveEvaluation:
    """Hard-enforce that net LTV >= baseline. If not, return empty bundle."""
    if evaluation.net_ltv >= baseline_ltv:
        return evaluation

    return ProfileIncentiveEvaluation(
        profile_id=evaluation.profile_id,
        selected_incentives=[],
        gross_ltv=baseline_ltv,
        estimated_cost=0.0,
        net_ltv=baseline_ltv,
        reasoning=f"Bundle dropped: net LTV (${evaluation.net_ltv:.2f}) < baseline (${baseline_ltv:.2f}). No incentives assigned.",
    )


def _persist_state(state: "OptimizationState"):
    """Save optimization state to Firestore (best-effort, swallow errors)."""
    if state.optimization_id in _deleted_optimization_ids:
        return
    try:
        fs_save_optimization(state)
    except Exception:
        pass  # Don't let Firestore errors crash the optimization


def _linear_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


def _is_statistically_converged(
    values: list[float],
    *,
    rel_std_threshold: float = 0.015,
    rel_slope_threshold: float = 0.002,
    rel_range_threshold: float = 0.03,
) -> bool:
    """Check convergence using rolling-window dispersion and trend tests.

    We declare convergence when:
    - coefficient of variation is small
    - normalized slope magnitude is small
    - normalized range over the window is small
    """
    n = len(values)
    if n < 3:
        return False

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(max(variance, 0.0))
    scale = max(abs(mean), 1e-6)
    rel_std = std / scale

    slope = _linear_slope(values)
    rel_slope = abs(slope) / scale

    rel_range = (max(values) - min(values)) / scale

    return (
        rel_std <= rel_std_threshold
        and rel_slope <= rel_slope_threshold
        and rel_range <= rel_range_threshold
    )


def _finalize_profile_result(
    state: "OptimizationState",
    profile: CanonicalProfile,
    best_final: ProfileIncentiveEvaluation,
    iterations_used: int,
) -> None:
    state.iterations_per_profile = iterations_used

    pop = profile.population_count or 1
    original_portfolio_ltv = profile.portfolio_ltv or (profile.ltv * pop)
    has_incentives = bool(best_final.selected_incentives)
    if has_incentives:
        new_gross_portfolio_ltv = best_final.gross_ltv * pop
        portfolio_cost = best_final.estimated_cost * pop
        new_net_portfolio_ltv = best_final.net_ltv * pop
    else:
        # Keep baseline columns internally consistent when no incentives are assigned.
        new_gross_portfolio_ltv = original_portfolio_ltv
        portfolio_cost = 0.0
        new_net_portfolio_ltv = original_portfolio_ltv

    result = OptimizationResult(
        profile_id=profile.profile_id,
        selected_incentives=best_final.selected_incentives if best_final.selected_incentives else ["None"],
        original_portfolio_ltv=original_portfolio_ltv,
        new_gross_portfolio_ltv=new_gross_portfolio_ltv,
        portfolio_cost=portfolio_cost,
        new_net_portfolio_ltv=new_net_portfolio_ltv,
        lift=new_net_portfolio_ltv - original_portfolio_ltv,
        reasoning=best_final.reasoning,
    )
    state.results.append(result)
    state.active_profile_id = ""
    state.active_profile_iteration = 0
    state.active_profile_no_improve = 0
    state.active_profile_best_net_ltv = float("-inf")
    state.active_profile_best_eval = None
    state.active_profile_net_history = []


def _process_profile(
    state: "OptimizationState",
    profile: CanonicalProfile,
    cost_map: dict[str, float],
    *,
    total_profiles: int,
) -> bool:
    """Advance one iteration for a profile.

    Returns True when the profile has converged/completed and result was finalized.
    """
    max_iterations = max(5, int(state.max_iterations or 50))
    patience = max(2, int(state.patience or 3))
    convergence_window = max(4, min(int(state.convergence_window or 6), max_iterations))
    min_iterations = min(max(convergence_window, patience + 3), max_iterations)
    # Treat tiny fluctuations as noise to avoid endlessly resetting patience.
    improvement_eps = max(0.1, abs(profile.ltv) * 0.0002)

    if state.active_profile_id != profile.profile_id:
        state.active_profile_id = profile.profile_id
        state.active_profile_iteration = 0
        state.active_profile_no_improve = 0
        state.active_profile_best_net_ltv = float("-inf")
        state.active_profile_best_eval = None
        state.active_profile_net_history = []

    iteration = state.active_profile_iteration + 1
    if iteration > max_iterations:
        iteration = max_iterations

    evaluation = evaluate_incentive_bundle(profile, state.available_incentives, cost_map)
    final = _enforce_baseline(evaluation, profile.ltv)
    state.active_profile_iteration = iteration
    state.active_profile_net_history.append(final.net_ltv)

    if final.net_ltv >= (state.active_profile_best_net_ltv + improvement_eps):
        state.active_profile_best_net_ltv = final.net_ltv
        state.active_profile_best_eval = final.model_dump()
        state.active_profile_no_improve = 0
    else:
        state.active_profile_no_improve += 1

    should_finalize = False
    finalize_reason = ""
    if iteration >= max_iterations:
        should_finalize = True
        finalize_reason = "max_iterations"
    elif iteration >= min_iterations:
        recent = state.active_profile_net_history[-convergence_window:]
        # Primary early-stop: statistical stabilization of recent outcomes.
        if _is_statistically_converged(recent):
            should_finalize = True
            finalize_reason = "converged"
        # Secondary early-stop: no meaningful improvement for long enough.
        elif state.active_profile_no_improve >= patience and len(recent) >= convergence_window:
            should_finalize = True
            finalize_reason = "patience"

    if not should_finalize:
        # Report smooth progress while iterating within the current profile so
        # the UI does not appear frozen at the previous whole-profile boundary.
        if total_profiles > 0:
            fractional_profile_progress = min(float(iteration) / float(max_iterations), 0.999)
            overall = ((state.next_profile_index + fractional_profile_progress) / float(total_profiles)) * 100.0
            state.progress = max(state.progress, min(99, int(math.ceil(overall))))
        state.current_step = (
            f"Evaluating {profile.profile_id} "
            f"({state.next_profile_index + 1}) - iter {iteration}/{max_iterations}..."
        )
        _persist_state(state)
        return False

    if state.active_profile_best_eval is not None:
        best_final = ProfileIncentiveEvaluation.model_validate(state.active_profile_best_eval)
    else:
        best_final = ProfileIncentiveEvaluation(
            profile_id=profile.profile_id,
            selected_incentives=[],
            gross_ltv=profile.ltv,
            estimated_cost=0.0,
            net_ltv=profile.ltv,
            reasoning="No valid optimization iterations completed; baseline retained.",
        )

    if finalize_reason == "converged":
        state.current_step = f"Converged for {profile.profile_id}; moving to next profile."
    elif finalize_reason == "patience":
        state.current_step = f"No meaningful improvement for {profile.profile_id}; moving to next profile."
    else:
        state.current_step = f"Reached max iterations for {profile.profile_id}; moving to next profile."
    _finalize_profile_result(state, profile, best_final, state.active_profile_iteration)
    return True


def advance_optimization(optimization_id: str, *, profiles_per_tick: int = 1) -> Optional["OptimizationState"]:
    """Advance a running optimization in small chunks.

    This avoids relying on background threads, which are unreliable in
    serverless HTTP runtimes after the request returns.
    """
    state = _optimizations.get(optimization_id)
    if not state:
        state = fs_load_optimization(optimization_id)
        if state:
            _optimizations[optimization_id] = state
    if not state:
        return None

    try:
        if state.status != "running":
            return state
        if state.cancelled:
            state.status = "cancelled"
            state.current_step = "Optimization cancelled by user."
            state.completed_at = datetime.utcnow()
            _persist_state(state)
            return state

        catalog = load_catalog(state.catalog_version)
        if not catalog:
            raise ValueError(f"Catalog {state.catalog_version} not found")

        total_profiles = len(catalog.profiles)
        if total_profiles == 0:
            state.status = "failed"
            state.error = "Catalog has no profiles to optimize."
            state.current_step = "Optimization failed."
            state.completed_at = datetime.utcnow()
            _persist_state(state)
            return state

        cost_map = get_incentive_cost_map(state.available_incentives)
        processed = 0

        while state.next_profile_index < total_profiles and processed < profiles_per_tick:
            if state.cancelled:
                state.status = "cancelled"
                state.current_step = "Optimization cancelled by user."
                state.completed_at = datetime.utcnow()
                _persist_state(state)
                return state

            profile = catalog.profiles[state.next_profile_index]
            state.current_step = f"Evaluating {profile.profile_id} ({state.next_profile_index + 1}/{total_profiles})..."
            _persist_state(state)
            profile_done = _process_profile(
                state,
                profile,
                cost_map,
                total_profiles=total_profiles,
            )
            if profile_done:
                state.next_profile_index += 1
                processed += 1
                state.progress = int((state.next_profile_index / total_profiles) * 100)
                _persist_state(state)
            else:
                # Return quickly so client can poll incremental progress.
                return state

        if state.next_profile_index >= total_profiles:
            state.status = "completed"
            state.progress = 100
            state.current_step = "Optimization completed."
            state.completed_at = datetime.utcnow()
            _persist_state(state)

    except Exception as e:
        state.status = "failed"
        state.error = str(e)
        state.current_step = "Optimization failed."
        state.completed_at = datetime.utcnow()
        _persist_state(state)
    return state

def start_optimization(catalog_version: str, *,
                     max_iterations: int = 50,
                     patience: int = 3,
                     incentive_set_version: str | None = None) -> str:
    # Load the incentive set (specific version or default)
    if incentive_set_version:
        inc_set = fs_load_incentive_set(incentive_set_version)
        if not inc_set:
            raise ValueError(f"Incentive set '{incentive_set_version}' not found")
    else:
        inc_set = load_or_seed_default()

    incentives_snapshot = [inc.model_dump() for inc in inc_set.incentives]

    optimization_id = str(uuid.uuid4())
    _deleted_optimization_ids.discard(optimization_id)
    state = OptimizationState(
        optimization_id=optimization_id,
        catalog_version=catalog_version,
        incentive_set_version=inc_set.version,
        status="running",
        progress=0,
        current_step="Initializing...",
        iterations_per_profile=0,  # updated per-profile during run
        available_incentives=incentives_snapshot,
        max_iterations=max(5, int(max_iterations)),
        patience=max(2, int(patience)),
        convergence_window=max(4, min(8, int(patience) + 3)),
        started_at=datetime.utcnow()
    )
    _optimizations[optimization_id] = state
    # Persist initial state so polling endpoints can find it immediately
    _persist_state(state)

    return optimization_id

def get_optimization_status(optimization_id: str) -> Optional[OptimizationState]:
    """Check in-memory first, then fall back to Firestore."""
    state = _optimizations.get(optimization_id)
    if state:
        return state
    return fs_load_optimization(optimization_id)

def cancel_optimization(optimization_id: str) -> bool:
    """Request cancellation of a running optimization."""
    state = _optimizations.get(optimization_id)
    if not state:
        state = fs_load_optimization(optimization_id)
        if state:
            _optimizations[optimization_id] = state
    if not state or state.status != "running":
        return False
    state.cancelled = True
    state.status = "cancelled"
    state.current_step = "Optimization cancelled by user."
    state.completed_at = datetime.utcnow()
    _persist_state(state)
    return True

# ---- Optimization persistence (Firestore) ----

def save_optimization(optimization_id: str) -> str | None:
    """Persist a completed optimization to Firestore. Returns optimization_id or None."""
    state = _optimizations.get(optimization_id)
    if not state:
        state = fs_load_optimization(optimization_id)
    if not state or state.status not in ("completed", "cancelled"):
        return None
    fs_save_optimization(state)
    return state.optimization_id

def delete_optimization(optimization_id: str) -> bool:
    """Remove optimization from memory and Firestore."""
    _deleted_optimization_ids.add(optimization_id)
    removed = _optimizations.pop(optimization_id, None)
    fs_removed = fs_delete_optimization(optimization_id)
    return removed is not None or fs_removed


def list_optimizations(catalog_version: str | None = None) -> list[dict]:
    """List saved optimizations from Firestore, optionally filtered by catalog_version."""
    return fs_list_optimizations(catalog_version)


def load_optimization(optimization_id: str) -> OptimizationState | None:
    """Load a saved optimization from Firestore."""
    return fs_load_optimization(optimization_id)
