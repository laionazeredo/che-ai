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
- **Dependency Management**: Use `uv` or `poetry`. Keep a clean `pyproject.toml`.
- **Testing**: Use `pytest`. Leverage fixtures and `pytest-asyncio`. Aim for high coverage of business logic.

## 🛡 Security & Error Handling
- **Errors**: Define custom exception hierarchies. Use `try...except` blocks with specific exceptions.
- **Security**: Avoid `eval()` and `exec()`. Sanitize inputs to prevent injection. Use `TruffleHog` for secret scanning.

## 🔗 References
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [Python Asyncio Tutorial](https://docs.python.org/3/library/asyncio.html)
