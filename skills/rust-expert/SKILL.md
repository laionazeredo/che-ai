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
- **Safety**: Run `cargo clippy` and `cargo fmt` religiously.

## 🔗 References
- [The Rust Book](https://doc.rust-lang.org/book/)
- [Tokio Documentation](https://tokio.rs/tokio/tutorial)
- [Leptos Documentation](https://leptos.dev/)
