---
name: "python-expert"
description: "Master guide for modern Python development. Covers code style, async/await patterns, FastAPI, Pydantic, type safety, testing, performance, and project structure."
---

# Python Expert Guide

This skill provides a unified set of rules and best practices for high-performance, type-safe Python development.

## 🐍 Modern Python Standards
- **Python 3.12+**: Use the latest features like PEP 695 type aliases and improved f-strings.
- **Type Safety**: Use `mypy` or `pyright`. Favor `Annotated`, `Generic`, and `Protocol` for structural typing.
- **Style**: Follow PEP 8 via `ruff`. Use meaningful variable names and docstrings (Google or NumPy style).

## ⚡ Async & Performance
- **Asyncio**: Use `async`/`await` for I/O-bound tasks. Avoid blocking calls in the event loop (use `run_in_executor` if necessary).
- **Patterns**: Use `asyncio.TaskGroup` (Python 3.11+) for structured concurrency.
- **Optimization**: Profile with `cProfile` or `py-spy`. Use `slots` to reduce memory footprint in high-frequency objects.

## 🚀 FastAPI & Pydantic
- **FastAPI**: Use Dependency Injection for services and DB sessions. Use `BackgroundTasks` for non-blocking side effects.
- **Pydantic**: Use V2 models. Leverage `Field` for validation and `computed_field` for derived properties.
- **Validation**: Strict validation by default. Use `BaseModel` and `ConfigDict`.

## 🏗 Project Structure & DevOps
- **Structure**: Use a `src/` layout. Define public APIs in `__init__.py` using `__all__`.
- **Dependency Management**: `uv` DEFAULT when `uv.lock` exists (beats pip/poetry/PDM; see CHE_RULES §XI E02 Matrix TABLE 2 row 715 uv P0 B02 gap). Pip/poetry only when legacy repo has no uv files. Keep a clean `pyproject.toml` with `[project]` PEP 621 metadata (not `[tool.poetry]` when uv is active).
  - **uv commands order (canonical)**: `uv venv` (create) · `uv sync` (install from lock, CI default, deterministic) · `uv add <pkg>` (add + update lock) · `uv add --dev pytest ruff` · `uv run python -m pytest` (runs in env without manual activate) · `uv lock --upgrade-package pandas` (safe upgrade one dep).
  - **`uv run` = ALWAYS prefer over direct python** in scripts/CI: ensures you are in the lock-matching environment even if `source venv/bin/activate` was forgotten.
  - **CI pipeline with uv**:
    ```yaml
    - uses: astral-sh/setup-uv@v3
    - run: uv sync --frozen  # EXACT lock match or FAIL (reproducibility non-negotiable)
    - run: uv run ruff check .
    - run: uv run pytest -q
    ```
- **Testing**: Use `pytest` (deep patterns below). Leverage `pytest-asyncio>=0.23` with `asyncio_mode=auto` (no `@pytest.mark.asyncio` boilerplate). Aim for high coverage of business logic.

## 🧪 Testing — pytest DEEP patterns (fixtures · parametrize · scopes · async)

(CHE_RULES §XI E02 · close superficial L28 pytest mention)

- **Fixture scopes (performance critical)**: Prefer highest-possible scope without leaking state. Order:
  - `scope="session"` (once per run): DB engine, HTTP test client to local FastAPI.
  - `scope="module"` (once per .py file): big shared fixtures that do NOT mutate, like a seeded read-only test-user dictionary.
  - `scope="function"` default (per test): anything that writes data to DB or mutates global state → fresh copy each test (isolation = no flaky).
- **Parametrize for table-driven behaviour tests** (equivalent to Go table-driven):
  ```python
  @pytest.mark.parametrize(
      "price_dollars,country_code,expected_tax_gbp",
      [
          (100, "GB", 20.0),   # happy UK VAT 20%
          (0,   "GB", 0.0),    # zero = no tax
          (100, "US", 0.0),    # US outside EU VAT
          (-5,  "GB", ValueError),  # negative price raises
      ],
      ids=["happy-uk", "zero", "us-outside", "negative-raises"],
  )
  def test_calculate_vat(price_dollars, country_code, expected_tax_gbp):
      ...
  ```
  Always add `ids=` so CI failure output names the case (`FAILED test_calculate_vat[negative-raises]`) instead of `[3]`.
- **tmp_path_factory for file-based tests**: Prefer built-in `tmp_path` (per test) or `tmp_path_factory.mktemp("x")` (session-scoped temp folder) over manual `tempfile.mkdtemp`. Pytest auto-deletes after run.
- **`pytest-asyncio scopes`**: For async fixtures that hit DB, use `@pytest.fixture(scope="session")` with matching `@pytest_asyncio.fixture(loop_scope="session")` → avoid spinning up 1 event loop per test (100× speedup on suites with 500+ async tests).
- **`monkeypatch` (built-in) vs `unittest.mock.patch`**: Default to `monkeypatch` for env vars / simple attribute swaps. Use `patch` only when you need `assert_called_once_with()` on complex call signatures. Never leave a patch active across tests (use `with patch(...)` context manager or fixture yield + cleanup).

## ⚡ Async & Performance — ADVANCED asyncio patterns (E02 B02 gap · close shallow L16-L18)

- **TaskGroup (Python 3.11+) = DEFAULT for fan-out concurrency**. Replace raw `asyncio.gather(*tasks)` with:
  ```python
  async with asyncio.TaskGroup() as tg:
      user_tasks = [tg.create_task(fetch_user(id)) for id in user_ids]
  users = [t.result() for t in user_tasks]  # results in order; ANY exception cancels rest
  ```
  **Why TaskGroup over gather?** (1) cancels siblings on first exception (no dangling tasks running in background — leak-prevention), (2) gives you task objects for introspection, (3) integrates well with `asyncio.timeout` per-group.
- **Semaphore to bound I/O concurrency (anti-DDoS your own DB/HTTP)**:
  ```python
  sem = asyncio.Semaphore(16)  # never more than 16 concurrent Postgres/HTTP in flight
  async def bounded_fetch(url):
      async with sem:
          return await httpx.get(url)
  ```
  Bounds: Postgres ≤ pool.max_connections · HTTP ≤ 32–128 · gRPC ≤ 2x CPU.
- **`asyncio.timeout(duration)` per-operation, NOT global**:
  ```python
  try:
      async with asyncio.timeout(2.5):  # 2.5s wall clock for THIS API call
          r = await client.get(url)
  except TimeoutError:
      return {"error": "upstream_timeout", ...}  # NEVER bubble raw TimeoutError to user
  ```
- **Blocking calls in async path → ALWAYS `asyncio.to_thread(...)`**: Never call `time.sleep(5)`, `pd.read_csv(huge_file)`, CPU-bound regex directly inside `async def` — blocks the entire event loop, latency of every other request shoots to 10s. Use:
  ```python
  # Good: offload blocking file parse to thread pool
  df = await asyncio.to_thread(pd.read_parquet, path, columns=["a","b"])
  ```
- **Retry + exponential backoff for transient network failures** (DB deadlock, 5xx upstream, network blip): Use `tenacity` (or a small util) with `wait=wait_random_exponential(multiplier=1, max=10)` + `stop=stop_after_attempt(5)`. Retry ONLY idempotent operations (GETs, retriable DB tx, external payment capture retry-with-idempotency-key). NEVER retry POST if upstream may have already accepted it.

## 📊 Jupyter DSML Patterns (E02 B02 gap · TABLE 2 row 716 Jupyter ZERO → partial)

- **Notebooks = EXPERIMENT ARTIFACTS, not production code.** Folder structure: `notebooks/YYYY-MM-DD-slug.ipynb` (date-prefixed for reproducibility timeline). `src/` = PRODUCTION code.
- **2+ cell rule for EVERY non-trivial notebook**:
  1. Cell #1 (SETUP, ALWAYS THE SAME):
     ```python
     %load_ext autoreload
     %autoreload 2
     from pathlib import Path; PROJECT_ROOT = Path("..").resolve()
     ```
     `autoreload 2` means edits to `src/` reflect in notebook WITHOUT kernel restart.
  2. Last cell (REPRODUCIBILITY STAMP):
     ```python
     import sys, platform, datetime; print(f"Run: {datetime.datetime.utcnow().isoformat()}Z"); print(f"Python: {sys.version}"); print(f"OS: {platform.platform()}"); import pandas; print(f"pandas: {pandas.__version__}")
     ```
     When bugs appear 1 month later, you know exactly which versions produced the chart.
- **Datasets: ALWAYS cache intermediate artifacts to disk between heavy steps.** Raw → cleaned → featurized → trained → scored. Save Parquet/Feather, never CSV for dataframes > 10k rows (Parquet = 1/20 size + type-preserving + 20× faster load).
- **`nbqa` for CI quality over notebooks**: Run `nbqa ruff notebooks/` + `nbqa isort notebooks/`. Prevents committing notebooks with: star imports, leftover `print("here debug")`, unused variables, `!pip install` leftover cells.
- **Deterministic random seeds**: At top of training notebook:
  ```python
  import random; random.seed(42)
  import numpy as np; np.random.seed(42)
  import torch; torch.manual_seed(42)
  ```
  Different runs = same numbers (unless you explicitly change seed).
- **No raw PII in notebooks**: If the data contains emails/phone/names → use the same `NOTIFICATION_PII_HASH_SECRET` hashing (from engineering-contracts §19 PII rules) BEFORE saving parquet to notebook cache folder.

## 🔗 LangSmith Tracing & Datasets (E02 B02 gap · TABLE 2 row 717 LangSmith ZERO → partial)

- **LangSmith = default when `LANGSMITH_API_KEY` in env (ai-agent-orchestrator skill §TESTING & OBSERVABILITY companion rule)**:
  ```python
  # Top-level, BEFORE any LangChain/LangGraph imports:
  import os; os.environ.setdefault("LANGSMITH_TRACING", "true")
  # Do NOT hardcode key here; load via env parser (zod/dynaconf) per engineering-contracts §17 env declaration
  ```
  With `LANGSMITH_TRACING=true` + API key set: every chain/graph run = auto-traced, no manual `with tracing_v2_enabled(...)`.
- **`traceable` decorator for CUSTOM (non-Lang) functions**:
  ```python
  from langsmith import traceable

  @traceable(name="DB GetOrderById", run_type="tool", metadata={"layer": "persistence"})
  async def get_order_by_id(db, order_id):
      ...
  ```
  Lets you see custom DB/HTTP calls inside the trace waterfall.
- **LangSmith Datasets + Evaluators = CI-grade regression tests for agents (not just unit-test pytest)**:
  1. `ls dataset create --name orders-refund-v1 --description "AC-12 refund scenarios"`
  2. Upload 20–50 (input, expected_output, metadata) rows via the LangSmith UI or `Client().create_examples(...)`.
  3. CI job: `ls run evaluate <dataset> -c my_agent_graph:run --evaluators cot_qa,labeled_score_string` — fails CI if accuracy drops below threshold (S14 engineering gates companion).
- **Trace-id correlation with che's structured logger**: Append `trace_id` from LangSmith `Run` object to the `traceId` structured-log field of engineering-contracts §19 Logging Standard → ONE id links agent trace → logs → OTel spans.

---

## 🐍 B-P1 Python · DSPy Compile-Time + Dataframe-Oriented + Env (E02 §XI P1 coverage 70% → ~80%)

### DSPy Agents Compile-Time Program Optimisation (agents/DSML production-grade)
LangChain = orchestration glue, DSPy = **learning compiler for prompts**. If you write 12 prompts for 12 edge cases = legacy. Use DSPy signatures + BootstrapFewShot + MIPROv2 optimizer:
```python
import dspy
class RefundClassifier(dspy.Signature):
    """Classify refund request into approved|rejected|manual with rationale."""
    order_id: str = dspy.InputField(desc="6+ char alphanumeric order id")
    user_message: str = dspy.InputField(desc="raw user ticket text")
    decision: dspy.Literal["approved","rejected","manual"] = dspy.OutputField()
    rationale: str = dspy.OutputField(desc="Why < 80 words, cites refund policy section")

turbo = dspy.OpenAI(model="gpt-4o-mini", max_tokens=300)
dspy.configure(lm=turbo)
classifier = dspy.ChainOfThought(RefundClassifier)
# Compile step = MANDATORY in CI for any production DSPy program:
from dspy.teleprompt import MIPROv2
compiled = MIPROv2(metric=accuracy_metric, prompt_model=turbo).compile(
    classifier, trainset=train_examples_50, valset=val_20,
)
# Compiled is ~60% more accurate than raw ChainOfThought. Save ARTIFACT to disk:
compiled.save("compiled/refund-classifier-v3.dspy.json")
```
**CI Gate NON-NEGOTIABLE for DSPy agents**: CI step runs `compiled.evalset(test_50)` and FAILS build if accuracy drops > 3pp below baseline (per CHE_RULES §X S14 LEAN SLO companion).

### Polars + DuckDB hybrid OLAP (replace pandas 70% use-cases)
| If you have… | Use… | Reason |
| --- | --- | --- |
| Tabular data < 2GB in-memory | **Polars lazy** | 5–10× faster than pandas, SIMD vectorized, zero-copy slices, `.collect()` only at end |
| Data > RAM / Parquet lake 100GB+ | **DuckDB `read_parquet('s3://...')`** | Single file OLAP engine · No server · PyArrow zero-copy · CBO with pushdown filters |
| Python ETL job 10 steps joins groupbys | **Polars plan → DuckDB exec via `duckdb.sql(pl.to_arrow())`** | Write plan in Polars familiar API, execute via DuckDB MPP engine. 1–2 orders faster than pandas. |
NON-NEGOTIABLE Polars pattern: ALWAYS build `.lazy()` FIRST, then `.collect(streaming=True)` last. NO `.collect()` mid-pipeline (forces full materialization = 10× mem blowup).
```python
# Right:
lazy_df = (pl.scan_parquet("events/*.parquet")
    .filter(pl.col("start_at") >= date(2027,1,1))
    .join(users.lazy(), left_on="owner_id", right_on="id", how="left")
    .group_by("region").agg(pl.sum("revenue").alias("rev"))
    .sort("rev", descending=True))
final = lazy_df.collect(streaming=True)   # streaming = out-of-core, fits in 8GB RAM for 100GB data
```
**DuckDB 8.0+**: For prod analytics scripts ALWAYS `SET memory_limit='6GB'; SET threads=8;` at top of script — prevents OOM killing CI runners with 8GB default.

### Ruff `--select I` Import Order + Pydantic-Settings ENV
- **Ruff I import sorting** REPLACES isort + reorder-python-imports. Add `select = ["I"]` to `pyproject.toml` [tool.ruff.lint]. Order: stdlib → 3rd-party → local project. Enforced in CI. Deviation = LEAN_penalty +1/file.
- **Pydantic-Settings ENV default parser** (over python-dotenv). Dotenv files SHOULD only be used LOCAL. Production env = AWS SSM / Vercel / Kubernetes downward API. Schema:
  ```python
  from pydantic_settings import BaseSettings, SettingsConfigDict
  class Settings(BaseSettings):
      model_config = SettingsConfigDict(env_prefix="APP_", extra="forbid")
      env: Literal["dev","staging","prod"]
      db_url: PostgresDsn
      concurrency: int = 32
  settings = Settings()   # NONE of these are str → typed. unknown APP_ var raises ValidationError immediately.
  ```

## References🛡 Security & Error Handling
- **Errors**: Define custom exception hierarchies. Use `try...except` blocks with SPECIFIC exceptions (bare `except:` = prohibited, equivalent to catch-all `Exception` OK only in top-level HTTP middleware with full traceback logged).
- **Security**: Avoid `eval()` and `exec()`. Sanitize inputs to prevent injection. Use `TruffleHog` for secret scanning.

## 🔗 References
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [Python Asyncio Tutorial](https://docs.python.org/3/library/asyncio.html)
