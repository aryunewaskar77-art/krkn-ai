# Krkn-AI Contribution Tracker

This document tracks the progress of Pull Requests (PRs) and Issues raised for the `krkn-ai` repository, along with suggestions for future improvements.

## 🚀 Raised Pull Requests & Issues

| ID | Type | Description | Status | Reference |
|:---|:---|:---|:---|:---|
| #204 | PR | README Documentation Fixes (Corrected output directory structure) | Merged / Active | [Conversation ffcf27f7] |
| #206 | PR | Addressed erroneous commits and synchronized documentation | Active | [Conversation ffcf27f7] |
| DOC-1 | Issue | Update CLI help documentation for better clarity | Planned | [Conversation 2d2dd329] |
| DOC-2 | Issue | Correct configuration examples in README/docs | Planned | [Conversation 2d2dd329] |
| DOC-3 | Issue | Standardize and refine the contributing guide | Planned | [Conversation 2d2dd329] |
| AUD-1 | Report | Full Technical Audit (Security, GA Logic, K8s Integration) | Completed | [Conversation fe5761de] |

---

## 💡 New Suggestions (High Quality)

Below are two high-impact suggestions for new issues/PRs to improve the codebase's performance and robustness.

### 1. [FEATURE/REFACTOR] Asynchronous Health Check Implementation
**Priority:** High | **Complexity:** Medium

**Description:**  
Currently, `HealthCheckWatcher` uses synchronous `requests` inside multiple `threading.Threads`. This approach is resource-heavy and less efficient for I/O-bound tasks like periodic network checks.

**Proposed Changes:**
- Refactor `HealthCheckWatcher` to use `asyncio` and `httpx` or `aiohttp`.
- Replace the thread-based polling loop with an asynchronous event loop.
- Use `asyncio.gather()` to run health checks concurrently.
- **Benefits:** Significant reduction in memory overhead, better scalability for many monitored URLs, and elimination of manual thread management/locking concerns.

---

### 2. [FEATURE] Implement Tournament Selection Strategy
**Priority:** Medium | **Complexity:** Medium

**Description:**  
The `GeneticAlgorithm` currently implements "Roulette Wheel Selection". While standard, it can suffer from premature convergence. A "Tournament Selection" strategy is often more robust against fitness noise and allows for easier adjustment of "selection pressure."

**Proposed Changes:**
- Implement the `tournament_selection` method in `krkn_ai/algorithm/genetic.py` (resolving the existing TODO on line 617).
- Add a new configuration parameter `selection_strategy` (enum: `roulette`, `tournament`) and `tournament_size`.
- Update `select_parents` to use the chosen strategy.
- **Benefits:** Improved optimization results in diverse scenarios and fulfillment of a codebase architectural goal.

---

## 📝 Next Steps
1. Create GitHub issues for the above suggestions to discuss with maintainers.
2. Branch out from `main` to implement the Asynchronous Refactor first.
