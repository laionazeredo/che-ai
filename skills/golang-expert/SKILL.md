---
name: "golang-expert"
description: "Universal expert guide for Golang development. Covers code style, concurrency, context, data structures, database access, design patterns, documentation, error handling, naming conventions, performance optimization, security, and testing."
---

# Golang Expert Guide

This skill is the definitive source for idiomatic Golang development, consolidating best practices across all engineering domains.

## 🛠 Core Principles
- **KISS & YAGNI**: Avoid premature abstraction. A little copying is better than a little dependency.
- **Composition over Inheritance**: Use interfaces to define behavior, not hierarchies.
- **Explicit over Implicit**: No hidden magic. Errors are values, not exceptions.

## 📏 Code Style & Naming
- **Naming**: Use `MixedCaps` (PascalCase/camelCase), no snake_case. Acronyms stay capitalized (e.g., `HTTPClient`).
- **Structure**: Package doc first, then imports, constants, types, constructors, methods.
- **Exporting**: Unexport aggressively. Only export what is necessary for the public API.
- **Formatting**: Always use `gofmt` or `gofumpt`.

## ⚡ Concurrency & Context
- **Goroutines**: Every goroutine must have a clear exit strategy (context or done channel).
- **Channels**: Share memory by communicating. Use unbuffered channels by default. Only senders close channels.
- **Context**: Pass `ctx context.Context` as the first parameter. Propagate it through all layers. Never store context in structs. Use `context.WithoutCancel` for background work that must outlive the request.

## 🗃 Data Structures & Performance
- **Slices**: Preallocate capacity with `make([]T, 0, cap)` when the size is known.
- **Maps**: Not thread-safe. Use `sync.Mutex` or `sync.Map` for concurrent access.
- **Performance**: Optimize only after profiling. Use `sync.Pool` for hot-path allocations.

## 🛡 Security & Error Handling
- **Errors**: Wrap errors with `%w` for context. Use `errors.Is` and `errors.As`.
- **Security**: Prevent SQL injection using parameterized queries. Use `gosec` for SAST.
- **PII**: Never log raw PII. Use structured logging (`slog`).

## 🧪 Testing
- **Table-Driven Tests**: Use anonymous structs for test cases.
- **Mocks**: Use interfaces to mock dependencies. Prefer `testify` for assertions.
- **Race Detection**: Always run tests with the `-race` flag.

## 🔗 References
- [Effective Go](https://go.dev/doc/effective_go)
- [Go Code Review Comments](https://github.com/golang/go/wiki/CodeReviewComments)
