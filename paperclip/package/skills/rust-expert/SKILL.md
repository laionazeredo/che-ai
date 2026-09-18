---
name: "rust-expert"
description: "Comprehensive guide for Rust development. Covers async patterns (Tokio), Axum, Leptos frontend, testing, and safety best practices."
---

# Rust Expert Guide

This skill provides the authoritative patterns for high-performance, memory-safe development in Rust.

## 🦀 Core Patterns & Safety
- **Ownership & Borrowing**: Leverage the borrow checker. Use `Clone` sparingly. Prefer `Box`, `Arc`, or `Rc` for shared ownership only when necessary.
- **Traits & Generics**: Design modular systems using Traits. Use `dyn Trait` for dynamic dispatch and `impl Trait` for static dispatch.
- **Error Handling**: Use `Result` and `Option`. Leverage `anyhow` for applications and `thiserror` for libraries.

## ⚡ Async Rust (Tokio & Axum)
- **Runtime**: Use `tokio` for async orchestration. Avoid blocking the event loop.
- **Web**: Use `axum` for building scalable, type-safe APIs. Leverage extractors and middleware.
- **Concurrency**: Use `tokio::spawn`, `select!`, and `JoinSet` for structured concurrency.

## 🎨 Leptos Frontend
- **Signals**: Use fine-grained reactivity via Signals. Avoid unnecessary re-renders.
- **SSR & Hydration**: Optimize for Server-Side Rendering and hydration. Use `Server Functions` for seamless client-server communication.
- **Components**: Build reusable, accessible components following the Leptos 0.8+ standards.

## 🧪 Testing & Quality
- **TDD**: Write unit and integration tests. Use `tokio::test` for async testing.
- **Mocking**: Use `mockall` or trait-based injection for dependency isolation.
- **Safety**: Run `cargo clippy` (all warnings + deny per CI) and `cargo fmt` religiously.

## 🗄 Database Layer (E03 Gaps B01 · Diesel / sqlx / SeaORM — see CHE_RULES §XI E03 Matrix TABLE 2 rows B01 #1-3)

### Diesel ORM (schema-first migrations + compile-time query builder)
- **Migration workflow**: `diesel setup` · `diesel migration generate <name>` (creates `up.sql` + `down.sql`) · `diesel migration run` (applies + regenerates `src/schema.rs`) · NEVER hand-edit `schema.rs`; always re-generated.
- **Connection pool**: Use `diesel::r2d2` (sync) or `diesel-async` + `bb8`/`deadpool` (async with `tokio-postgres` backend); PoolSize = CPU × 2 + 1 typical web. `DATABASE_URL` via env or `.env` (via `dotenvy` crate — never commit the actual values).
- **Query patterns**: Prefer `Queryable` + `Insertable` derive macros. Avoid `diesel::sql_query` raw unless 100% unavoidable multi-CTE analytics; if raw → always bind parameters (NEVER string interpolation).
- **Error handling**: `diesel::result::Error::NotFound` maps cleanly to `Option<T>` in service layer (domain Result, not raw Diesel errors leaked to HTTP handler).

### sqlx (SQL-first, compile-time checked without ORM)
- **Philosophy**: No ORM, no codegen from schema — `.sqlx` verifies queries against a live DB at compile time via `sqlx::query!` / `query_as!` macros. **Choose this when:** raw SQL control + zero boilerplate structs is valued higher than ORM query composability.
- **Offline mode**: Run `cargo sqlx prepare` → commits `sqlx-data.json` so CI/builds don't need a DB at compile time. THIS IS NON-NEGOTIABLE in any pipeline.
- **Pool + Acquire**: `sqlx::postgres::PgPoolOptions::new().max_connections(N).connect(&url).await?`. Always set `acquire_timeout` (e.g. 5s) to prevent cascading hangs.
- **Migrations**: `sqlx migrate add <name>` + `migrate!(./migrations).run(&pool).await?` called at app startup (BEFORE accepting requests).
- **Transactions**: `pool.begin().await?` + `tx.commit().await?` pattern. Keep tx short: DB load = biggest factor in tail latency.

### SeaORM (async-first, entity-centric ORM — middle ground)
- **When to pick over Diesel/sqlx**: Hybrid apps where you want entity `DeriveEntityModel` scaffolding (`sea-orm-cli generate entity -u <URL> -o src/entities`) + still support raw SQL via `exec()` or custom `Statement`.
- **Backend runtime**: Always `runtime-tokio-rustls` (not `runtime-async-std`) unless the project is already async-std everywhere.
- **Connection**: `Database::connect(url).await?` or `ConnectOptions` for SQLx-level settings (`max_connections`, `sqlx_logging_level`).
- **CRUD + Select patterns**: `.find()` + `filter()` + `one()` / `all()` on `Entity`. For paginated list APIs → combine `cursor::Cursor` or `Paginator` (never fetch all in memory for > 100 rows).
- **Transaction**: `db.transaction::<_, _, DbErr>(|txn| Box::pin(async move { ... })).await`; return `Err(DbErr::Custom(..))` for rollback.

### Rust DB ORM Cheat-sheet — Which one?
| Criterion | sqlx (SQL first) | Diesel (ORM migrations first) | SeaORM (entities async first) |
| --- | --- | --- | --- |
| Query composability reuse across handlers | Low (SQL strings) | Very high (typed `.filter().inner_join()`) | High (Typed entities + custom Find) |
| Migrations DX | `sqlx migrate` lightweight | `diesel CLI` heavyweight but robust + schema.rs | `sea-orm-cli migrate` good middle |
| Works axum + tokio natively | Yes (first-class async) | Need `diesel-async` backend | Yes (tokio by default) |
| CI offline mode (no DB at build) | `sqlx prepare` → `sqlx-data.json` | N/A (diesel always needs DB or schema.rs at compile-time only for macros) | Entity files already generated locally |

## 🚂 Loco Framework (Rails-inspired Structured Backend — E03 B01 #4 loco structured framework)

- **Project scaffold**: `cargo install loco-cli` → `loco new myapp` selects starter: `_app` (full-stack SaaS auth + email + jobs) or `_api` (JSON API bare) or `_saas` (multi-tenant subscription).
- **Folder conventions (never restructure without strong reason)**: `src/app.rs` boot sequence · `src/controllers/` HTTP endpoints · `src/models/` entities (SeaORM under hood) · `src/views/` (tera templates if MVC) · `src/workers/` async BackgroundJob · `src/commands/` CLI custom (binaries) · `src/tests/` requests integration tests.
- **Migrations**: `cargo loco migrate` (wraps sea-orm-migrate). Always `generate` new migration vs edit existing already-ran ones (immutable).
- **Authentication middleware** `auth::JWT` / `auth::Cookie` extractors are used via `#[middleware]` macro; NEVER roll your own JWT validation.
- **Background workers**: For non-blocking work (email, webhooks) use `#[async_trait] impl BackgroundJob for MyJob` + `app.enqueue(MyJob {..}).await` + `WorkerKind::AsyncQueue` (Redis) OR `WorkerKind::InlineBlocking` (local dev fallback without Redis).
- **Mailers / Views**: Use `loco_mailer::Mailer` + `views/emails/` templates. NEVER hardcode HTML email inline in source.
- **Testing requests**: Tests in `src/tests/requests/*_test.rs` use `init_app().await` fixture to boot in-memory sqlite or isolated test-Postgres. Call `create_user(&authn, "role").await` pattern to fixture auth.

## ⚡ Async Rust — Axum DEEPENED (beyond basic today — State / Extractors / Middleware / Testing)

(Previous § bullets are kept for the Tokio primitives — this deepens Axum-specific patterns per E03 Matrix gap TABLE 2 row 718)

- **State injection** (`Router::with_state`) over global lazy-static: Define `struct AppState { db: PgPool, config: Arc<Config> }` in one place. Share `Arc<AppState>` across routers. Extract in handlers via `State(state): State<Arc<AppState>>` (never `&'static`). Makes testing + per-request overrides trivial.
- **Middleware order matters** (outer → inner = execution order):
  ```rust
  Router::new()
    .route("/api/items", get(list_items))
    .layer(TraceLayer::new_for_http()) // outer = request-id + timing
    .layer(from_fn_with_state(auth_state.clone(), require_auth_mw)) // auth BEFORE body parsing
    .layer(DefaultBodyLimit::max(2_000_000)) // 2MB
    .with_state(app_state);
  ```
- **Error mapping via `IntoResponse` + `thiserror`**: All service-layer errors implement `IntoResponse` → consistent JSON envelope `{ error: { code, message, trace_id? } }` with correct HTTP status. NEVER `unwrap()` in handler bodies (use `?` + `IntoResponse`).
- **Router merge + nesting**: Split `Router::new()` per domain (items_router(), users_router()) and `Router::new().nest("/api/v1", v1_router())`. Each child router has its own middlewares; parent state propagates down automatically.
- **Testing with `axum::test::RouterExt`**:
  ```rust
  let app = build_test_router().await; // in-memory DB, no network
  let resp = app.get("/api/items").await;
  assert_eq!(resp.status(), StatusCode::OK);
  let body: Vec<ItemDto> = resp.json().await;
  ```

## 🎨 Leptos Frontend DEEPENED (Full-stack SSR + Hydration strategies — E03 Matrix TABLE 2 row 719)

- **Leptos + Axum integration (`leptos_axum`)**: `leptos::view!` in client components · `#[server(MyActionFn)]` server functions auto-generate POST endpoint. ALWAYS set `#[server(endpoint = "/api/my-action")]` to keep HTTP paths stable & predictable.
- **`<ActionForm/>` = forms WITHOUT manual fetch**: Attach `server_fn` as action → `<ActionForm action=my_action>..inputs..</ActionForm>`. Progressive-enhance friendly (works with JS disabled → POST reload; with JS → instant optimistic UI).
- **Error propagation `ServerFnError`**: Server functions return `Result<T, ServerFnError<T>>`. Use `?` in server body + map app-specific errors to `ServerFnError::ServerError(..)` or custom `Err(MyError::X).into_server_fn_error()`.
- **Hydration strategies (performance critical)**:
  - Default: SSR full page + client-side hydrate whole. Use for simple marketing pages.
  - **Islands** (`leptos_islands`) = SSR-only outer page, hydrate ONLY interactive `#[component]` islands inside. This is THE recommended pattern for heavy content sites (docs, marketing, long-form). Hydration cost = proportional to interactivity count, NOT page size.
- **`<Title/>` + `<Meta/>` via `leptos_meta`:** Set per-route `<title>` + OG tags inside components via `<Title text=format!("{} | Site", product.name)/>`. Use `leptos_axum::render_app_to_stream_with_context` to inject meta tags SSR side.
- **Resources for async data fetching**: `let items = create_resource(move || (), |_| async { fetch_items().await });`. Render via `move || items.read().map(|res| match res { Ok(..) => view!{..}, Err(e) => view!{<p class="err">"Load failed"</p>}})`. NEVER `.await` directly inside a reactive `view!` (creates infinite rerender loops).

---

## 🦀 B-P1 Rust · Frameworks Extras + Perf (E03 §XI P1 coverage 45% → ~60%)

### HTTP Framework Decision (Axum DEFAULT 80%, Actix 15%, Poem 5%)
| Question | Pick | Why |
| --- | --- | --- |
| Starting a NEW generic REST/JSON API? | **Axum** (Tower + Hyper) | Official Tokio team · Extractors ergonomic · `IntoResponse` error pattern canon |
| Performance microbenchmark Sieve++ raw req/s? | **Actix-web v4** | Own `actix-rt` runtime · Slightly faster for <100µs handlers |
| OPENAPI-FIRST codegen required? | **Poem** (OpenAPI + poem-api) | Macro `#[oai(path=...)]` emits `openapi.json` 100% auto, no schema duplication |
**NON-NEGOTIABLE middleware 4-stack ALL 3 frameworks**: TraceLayer → CORS → BodyLimit → CompressionBr. Missing any 1 = LEAN_penalty S14 +2.

### Yew SPA SSR Hydration + Dioxus Cross-Platform (Heavy Content Frontend)
- **Yew 0.21 + SSR `yew::ServerRenderer`**: NEVER `function_component` with 1000 children without SSR. Render on server, hydrate skeleton only. Pattern:
  ```rust
  let html = ServerRenderer::<App>::new().render().await;
  // Return from Axum handler with content-type text/html
  ```
  `trunk build --release` 450KB default WASM = GZIP ~150KB acceptable. >600KB raw WASM = LEAN_penalty S14 +3.
- **Dioxus v0.5** (Web / Desktop / Mobile iOS+Android single source): Use `dioxus-fullstack` SSR + LiveView for internal admin panels that NEED desktop/mobile parity. Shared hooks: `use_future(|| async { fetch().await })` same across targets.

### tokio-console Performance Diagnosis (Production 1.4× slowdown root-cause)
Enable `--features tokio/unstable` + start `tokio-console` (6666 default). RED FLAGS in console = open investigation ticket:
1. **Busy poll % > 70% sustained** → task polling CPU loop, missing `.await` on blocking call (use `spawn_blocking` for read_file/send_mail — NEVER run `std::fs` on tokio runtime)
2. **Polls 100× higher than wakes** → fake wakeups, `tokio::select!` with `futures::stream::pending()` fallback branch
3. **Task runtime > 5 min without schedule end** → infinite loop / leak (use `tokio::time::timeout(Duration::from_secs(120), f)` boundary on EVERY external call)

## 🔗 References
- [The Rust Book](https://doc.rust-lang.org/book/)
- [Tokio Documentation](https://tokio.rs/tokio/tutorial)
- [Leptos Documentation](https://leptos.dev/)
