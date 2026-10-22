# Contributing

Thank you for your interest in contributing! This document outlines how you can participate.

## Code of Conduct

Be respectful and constructive. We welcome contributions from everyone.

## Getting Started

1. Fork the repository.
2. Create a feature branch from `main`.
3. Make your changes.
4. Run `uv run ruff check .` and `uv run pytest -q` to ensure everything passes.
5. Push your branch and open a pull request.

## Development Workflow

- Work on a separate branch: `git checkout -b feat/your-feature`
- Commit with conventional commits: `git commit -m "feat: your commit message"`
- Push and create a PR against `main`

## Testing

All tests must pass:

```bash
uv run pytest -q
```

## Code Style

- Follow the existing code style in the repository.
- Run `uv run ruff check .` to lint your changes.

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0-or-later license.

---

Thank you for contributing!
