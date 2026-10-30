# Contributing to runtfy

Thank you for contributing to **runtfy**! We welcome bug reports, documentation updates, and pull requests.

---

## Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/adilkt16/runtfy.git
   cd runtfy
   ```

2. **Install in editable mode with development dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

3. **Run the test suite**:
   ```bash
   python -m pytest tests/ -v
   ```

---

## Implementation Rules

Every contributor must adhere strictly to these core project rules:

1. **No hardcoded secrets or machine-specific paths**:
   - Never hardcode a topic, token, username, email, or absolute home directory path.
   - Always resolve home directories dynamically using `pathlib.Path.home()`.
2. **Never log or print the ntfy topic**:
   - The ntfy topic is considered private. Never print it in debug output, local logs, or test reports.
3. **No extraneous network calls**:
   - runtfy must not connect to telemetry, metrics, or third-party tracking services.
   - The only allowed network traffic is directly to the configured ntfy server.
   - All automated unit tests must mock external network calls.
4. **Use placeholders everywhere**:
   - Use generic placeholders (such as `your-topic-here` and `~/.config/runtfy`) across all documentation, error strings, and tests.
5. **Write tests for every change**:
   - Every bug fix, feature, and refactor must include corresponding unit tests. Run `python -m pytest tests/ -v` and ensure all tests pass before opening a PR.
6. **Ask before adding dependencies**:
   - runtfy prioritizes remaining lightweight and audit-friendly. Avoid introducing third-party runtime dependencies without prior discussion and approval.

---

## Submitting a Pull Request

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/my-feature-name
   ```
2. Make your changes adhering to the coding rules.
3. Run the full test suite and confirm 100% pass rate:
   ```bash
   python -m pytest tests/ -v
   ```
4. Verify that no secrets, machine paths, or personal emails are present in your diff:
   ```bash
   git diff
   ```
5. Commit your changes with clear, descriptive messages and submit a pull request on GitHub.
