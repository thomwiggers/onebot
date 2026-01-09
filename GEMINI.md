# OneBot

OneBot is an IRC bot based on `irc3`.

## Development Setup

This project uses `uv` for dependency management and `ruff` for code style.

### Prerequisites

- Python 3.11+
- `uv` (https://github.com/astral-sh/uv)

### Installation

1.  **Sync dependencies:**
    ```bash
    uv sync
    ```
    This creates a virtual environment and installs all dependencies (including dev dependencies).

## Code Standards

We use `ruff` for linting and formatting. Ensure all code is compliant before committing.

-   **Check code:**
    ```bash
    uv run ruff check .
    ```
-   **Format code:**
    ```bash
    uv run ruff format .
    ```

## Testing

Tests are written using `pytest`.

-   **Run tests:**
    ```bash
    uv run pytest
    ```
-   **Run full test suite (multi-environment):**
    ```bash
    uv run tox
    ```
    This uses `tox-uv` to test across supported Python versions.

## Project Structure

-   `onebot/`: Main package source code.
    -   `plugins/`: OneBot plugins (features like `lastfm`, `trakt`, `wolframalpha`, etc.).
    -   `__init__.py`: Entry point (`run` function).
-   `tests/`: Test suite.
    -   `fixtures/`: Test data (betamax cassettes, JSON responses).
-   `docs/`: Sphinx documentation.
-   `pyproject.toml`: Project configuration, dependencies, and tool settings.

## Common Tasks

### Adding a Dependency

```bash
uv add <package_name>
```

### Adding a Plugin

1.  Create a new file in `onebot/plugins/`.
2.  Implement the plugin class decorated with `@irc3.plugin`.
3.  Add tests in `tests/`.

### Building Documentation

```bash
cd docs
make html
```
