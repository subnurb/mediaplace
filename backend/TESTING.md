### Testing strategy (TDD-friendly)

This project uses `pytest` and `pytest-django` with tests organized by DDD layers.

---

### 1. Setup

**Dependencies** (already installed in `.venv`):
- `pytest >= 9.0`
- `pytest-django >= 4.12`

**Configuration** (`backend/pytest.ini`):
```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
pythonpath = .
addopts = -q --tb=short
```

**Run all tests:**
```bash
cd backend
source .venv/bin/activate
pytest
```

**Run domain tests only (fastest — no DB, no network):**
```bash
pytest tests/domain/ -v
```

---

### 2. Test organization

```text
backend/tests/
  domain/                              # Pure logic, no I/O
    test_sync_services.py              #   15 tests: push plan, error classification
    test_library_services.py           #   24 tests: normalization, grouping, merging rules
  application/                         # Orchestration with mocked infrastructure
    (test_sync_workflow.py)            #   TODO: mock platform APIs, verify orchestration
  infrastructure/                      # Contract tests against recorded responses
    (test_spotify_service.py)          #   TODO: mock Spotipy, verify API calls
```

**Domain tests** are the foundation — they verify business rules using plain Python data with no Django models or external services. They run in under 1 second.

**Application tests** (next priority) will use `pytest-django` with DB access and mock platform services to verify that orchestrators correctly:
- Call the right infrastructure adapters
- Pass the right data to domain services
- Persist the correct records

**Infrastructure tests** (lowest priority) will use recorded HTTP responses to verify that platform adapters correctly parse API data and handle errors.

---

### 3. What is tested today

| Layer | Module | Tests | What is verified |
|---|---|---|---|
| Domain | `domain.sync.services` | 15 | Track pushability rules, push plan filtering (excludes already-pushed, non-pushable), error classification for Spotify 403, token expiry, rate limiting, unknown errors |
| Domain | `domain.library.services` | 24 | Text normalization (lowercase, accents, parentheticals, punctuation), artist normalization (YouTube suffixes), title candidate generation, group key variants, cross-platform merge rules, field preference (pick longest) |

---

### 4. TDD workflow for new features

Follow the red-green-refactor cycle:

1. **Write a failing test** in the appropriate `tests/` directory.
2. **Implement the minimum code** to make it pass.
3. **Refactor** with confidence — tests catch regressions.

**Example: Adding a new sync rule**

```python
# tests/domain/test_sync_services.py
def test_tracks_with_failed_status_are_never_pushable():
    assert is_track_pushable("failed", "", "vid123") is False
    assert is_track_pushable("failed", "confirmed", "vid123") is False
```

Run → see it fail → implement the rule → see it pass → commit.

---

### 5. Running tests in CI

```yaml
# .github/workflows/test.yml (example)
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-django
          pytest --tb=short
```

---

### 6. Adding new tests — checklist

- [ ] Is the logic pure (no I/O)? → Put test in `tests/domain/`
- [ ] Does it require Django models? → Put test in `tests/application/`, use `@pytest.mark.django_db`
- [ ] Does it call external APIs? → Put test in `tests/infrastructure/`, mock HTTP calls
- [ ] Does the test name describe the *behavior*, not the implementation?
- [ ] Are edge cases covered (empty input, None values, error conditions)?
