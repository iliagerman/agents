---
name: project-init
description: >-
  Scaffold a new full-stack project with FastAPI backend, React + shadcn frontend,
  SQLAlchemy + Postgres database, documentation structure, justfile commands,
  and git hooks for smoke tests and automated code review/doc updates on push.
  Use when starting a new project from scratch.
---

# Project Init

Scaffold a complete full-stack project with backend, frontend, database, documentation, tooling, and git hooks.

## When to Use

- User asks to start a new project
- User asks to scaffold or bootstrap an application
- User wants to set up a full-stack app with FastAPI and React
- User asks to initialize a new codebase from scratch

## Workflow

Follow these phases in order. Wait for user input at each checkpoint before proceeding.

### Phase 0: Gather Project Details

1. Ask the user for:
   - **Project name** (kebab-case, used for directory and package names)
   - **Short description** (one sentence, used in README and CLAUDE.md)
   - **Postgres connection details** or whether to use a local Docker Postgres (default: Docker)
2. **CHECKPOINT**: Confirm project name, description, and DB strategy before proceeding.

### Phase 1: Directory Structure

Create the project root and full directory tree:

```
<project-name>/
  backend/
    app/
      api/
        routers/
          __init__.py
          health.py
      core/
        __init__.py
        config.py
        database.py
        exceptions.py
        logging.py
      dao/
        __init__.py
      enums/
        __init__.py
      models/
        __init__.py
      schemas/
        __init__.py
        base.py
      services/
        __init__.py
      utils/
        __init__.py
        http.py
      __init__.py
      main.py
    migrations/
      versions/
    tests/
      api/
      dao/
      services/
      conftest.py
    pyproject.toml
    alembic.ini
  client/
    public/
    src/
      components/
        ui/
        shared/
      contexts/
      features/
      hooks/
        queries/
      lib/
        utils.ts
      pages/
      services/
      styles/
        tokens.css
        globals.css
      types/
      App.tsx
      main.tsx
      vite-env.d.ts
    tests/
      integration/
      utils/
    index.html
    package.json
    tsconfig.json
    tsconfig.app.json
    tsconfig.node.json
    vite.config.ts
    postcss.config.js
    tailwind.config.ts
    eslint.config.js
    components.json
  docs/
    architecture.md
    api.md
    deployment.md
    development.md
  .github/
    workflows/
  CLAUDE.md
  justfile
  docker-compose.yml
  .gitignore
  .env.example
  README.md
```

### Phase 2: Backend Setup

1. **`pyproject.toml`** — Configure with UV as the package manager:
   ```toml
   [project]
   name = "<project-name>-backend"
   version = "0.1.0"
   requires-python = ">=3.12"
   dependencies = [
       "fastapi>=0.115.0",
       "uvicorn[standard]>=0.34.0",
       "sqlalchemy[asyncio]>=2.0.0",
       "asyncpg>=0.30.0",
       "alembic>=1.14.0",
       "pydantic>=2.10.0",
       "pydantic-settings>=2.7.0",
       "python-dotenv>=1.0.0",
   ]

   [project.optional-dependencies]
   dev = [
       "pytest>=8.0.0",
       "pytest-asyncio>=0.25.0",
       "httpx>=0.28.0",
       "ruff>=0.8.0",
   ]

   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   testpaths = ["tests"]

   [tool.ruff]
   line-length = 120
   target-version = "py312"

   [tool.ruff.lint]
   select = ["E", "F", "I", "N", "W", "UP", "B", "A", "SIM"]
   ```

2. **`app/main.py`** — FastAPI application entry point with CORS, exception handlers, and health endpoint.

3. **`app/core/config.py`** — Pydantic settings loading from environment variables:
   - `DATABASE_URL` (async Postgres connection string)
   - `CORS_ORIGINS` (list of allowed origins, default `["http://localhost:5173"]`)
   - `ENVIRONMENT` (development/staging/production)
   - `DEBUG` flag

4. **`app/core/database.py`** — SQLAlchemy async engine and session factory using `asyncpg`.

5. **`app/core/exceptions.py`** — Base `AppException` and common subclasses (`NotFoundError`, `ValidationError`, `AuthorizationError`) with global exception handler.

6. **`app/core/logging.py`** — Centralized logging configuration. This is the **only** place logging is configured in the entire application. All other modules use `from app.core.logging import get_logger`.

   **Requirements:**
   - Use Python's built-in `logging` module — no third-party logging libraries.
   - **Single `RotatingFileHandler`** writing to `logs/app.log` with `maxBytes=10_485_760` (10 MB) and `backupCount=0` — when the file hits 10 MB it is deleted and a fresh one starts. No `.1`, `.2` rotated copies.
   - A `StreamHandler` for console output (stdout).
   - Log level controlled by `settings.DEBUG` — `DEBUG` when true, `INFO` otherwise.

   **Structured log format** — every log line includes:
   - Timestamp (ISO 8601)
   - Log level
   - `correlation_id` — a unique ID that traces a single request across the entire call chain
   - `tenant_id` — the tenant the request belongs to (or `-` if not in a tenant context)
   - Logger name
   - Message

   Example format:
   ```
   2026-04-08T14:23:01.123Z | INFO | corr=abc123 | tenant=42 | app.services.user | User created successfully
   ```

   **Context propagation** — use `contextvars.ContextVar` to store `correlation_id` and `tenant_id`:
   ```python
   import contextvars

   correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")
   tenant_id_ctx: ContextVar[str] = ContextVar("tenant_id", default="-")
   ```

   A custom `logging.Filter` reads these context vars and injects them into every log record automatically.

   **`get_logger(name: str)`** — factory function that returns a logger with the filter already attached. All modules use this:
   ```python
   from app.core.logging import get_logger

   logger = get_logger(__name__)
   logger.info("Processing started")
   ```

   **FastAPI middleware** (`app/core/logging.py` or `app/main.py`) — a middleware that runs on every request and:
   1. Generates a `correlation_id` (UUID4) or reads it from the `X-Correlation-ID` header if provided.
   2. Extracts `tenant_id` from the authenticated user / token (or sets `-` for unauthenticated routes).
   3. Sets both into the context vars.
   4. Adds `X-Correlation-ID` to the response headers.
   5. Logs the request start (`method`, `path`, `tenant_id`) and request end (`status_code`, `duration_ms`).

   **`logs/` directory** — created automatically on startup if it doesn't exist. Add `logs/` to `.gitignore`.

7. **`app/schemas/base.py`** — `JsonModel` base class with `camelCase` alias generator and `from_()` / `to()` protocol, plus `MessageResponse`.

7. **`app/utils/http.py`** — `get_or_404()` and `require()` helpers.

8. **`app/api/routers/health.py`** — Health check endpoint returning `ServiceHealthResponse`.

9. **`alembic.ini`** and **`migrations/`** — Alembic configuration pointing to the async database URL.

10. **`tests/conftest.py`** — Fixtures for async test client (`httpx.AsyncClient`), in-memory or test database session, and test data factories.

### Phase 3: Frontend Setup

1. Initialize the React project using Vite:
   ```bash
   cd <project-name>/client
   npm create vite@latest . -- --template react-ts
   ```

2. Install core dependencies:
   ```bash
   npm install react-router-dom @tanstack/react-query axios
   npm install -D tailwindcss @tailwindcss/vite postcss autoprefixer
   npm install -D eslint @eslint/js typescript-eslint
   npm install -D @testing-library/react @testing-library/jest-dom @testing-library/user-event vitest jsdom
   npm install -D @playwright/test
   ```

3. Initialize and install shadcn:
   ```bash
   npx shadcn@latest init
   ```
   Select: New York style, Zinc color, CSS variables enabled.

4. **`src/styles/tokens.css`** — Design tokens (spacing, typography, color aliases).

5. **`src/styles/globals.css`** — Tailwind imports and base styles.

6. **`src/lib/utils.ts`** — `cn()` utility using `clsx` + `tailwind-merge`.

7. **`src/services/`** — Base API service class using `axios` with base URL from env, typed request/response methods.

8. **`src/App.tsx`** — Root component with `QueryClientProvider`, `BrowserRouter`, and route layout.

9. **`src/main.tsx`** — Entry point rendering `App` into DOM.

10. **`vite.config.ts`** — Configure `@/` path alias, Vitest, and dynamic backend proxy. The proxy target reads the backend port from `VITE_BACKEND_PORT` env var (set by the justfile), defaulting to `8000`:
    ```ts
    server: {
      proxy: {
        '/api': {
          target: `http://localhost:${process.env.VITE_BACKEND_PORT || 8000}`,
          changeOrigin: true,
        },
      },
    },
    ```

11. **`tsconfig.json`** / **`tsconfig.app.json`** — Path aliases matching Vite config.

12. **`eslint.config.js`** — ESLint flat config with TypeScript and React rules.

13. **`tests/integration/`** — Directory with a sample integration test.

14. **`tests/utils/`** — Test utilities directory.

### Phase 4: Database & Docker

1. **`docker-compose.yml`** — Postgres service with:
   - Named volume for data persistence
   - Health check
   - Port 5432
   - Environment variables for user, password, database name

2. **`.env.example`** — Template with all required environment variables:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/<project-name>
   CORS_ORIGINS=["http://localhost:5173"]
   ENVIRONMENT=development
   DEBUG=true
   ```

### Phase 5: Documentation

1. **`docs/architecture.md`** — High-level overview of the stack, layers, and data flow.

2. **`docs/api.md`** — API documentation template with endpoint listing format.

3. **`docs/deployment.md`** — Deployment guide template.

4. **`docs/development.md`** — Local development setup guide referencing the justfile commands.

5. **`CLAUDE.md`** — Project context for Claude:
   ```markdown
   # <Project Name>

   <Short description>

   ## ⚠️ MANDATORY: Test-Driven Development (TDD) Workflow

   This project follows a strict TDD workflow. Every new feature — backend or frontend — MUST follow this order:

   ### The TDD Rule: Tests FIRST, Code SECOND

   1. **Write failing tests** — Before writing ANY implementation code, write the tests that define the expected behavior.
   2. **Run the tests — confirm they fail** — Tests MUST fail before implementation exists. This proves the tests are actually testing something.
   3. **Write the minimum implementation** — Write only enough code to make the failing tests pass.
   4. **Run the tests — confirm they pass** — All new tests must pass. All existing tests must still pass.
   5. **Refactor if needed** — Clean up the implementation while keeping all tests green.

   ### Backend TDD Flow

   For every new backend feature:
   1. Write integration tests in `backend/tests/services/` or `backend/tests/dao/` that test the expected service/DAO behavior against a real database.
   2. Write API tests in `backend/tests/api/` that test the HTTP request/response cycle.
   3. Run `just test-backend` — confirm the new tests FAIL (no implementation yet).
   4. Implement the feature (schemas, DAOs, services, routers).
   5. Run `just test-backend` — confirm all tests PASS.

   ### Frontend TDD Flow

   For every new frontend feature:
   1. Write integration tests in `client/tests/integration/` using Vitest + React Testing Library that test component interactions and behavior.
   2. Write E2E tests in `client/tests/` using Playwright that test the full user flow.
   3. Run the tests — confirm the new tests FAIL (no implementation yet).
   4. Implement the feature (types, services, hooks, components, pages).
   5. Run the tests — confirm all tests PASS.

   ### What This Means in Practice

   - **NEVER** start by writing a component, service, router, or any implementation code.
   - **ALWAYS** start by writing the test file that describes what the feature should do.
   - If you are about to create a new file in `app/services/`, `app/api/routers/`, `src/components/`, `src/features/`, or `src/pages/` — STOP. Write the test first.
   - The only exception is pure scaffolding (types, enums, schemas) that tests may depend on.

   ## Stack

   - **Backend**: FastAPI + SQLAlchemy (async) + Postgres
   - **Frontend**: React + TypeScript + Vite + Tailwind + shadcn/ui
   - **Database**: PostgreSQL with Alembic migrations
   - **Package Management**: UV (Python), npm (Node)
   - **Task Runner**: just

   ## Architecture

   ### Backend (backend/)
   - `app/api/routers/` — HTTP endpoints (thin layer, delegates to services)
   - `app/services/` — Business logic
   - `app/dao/` — Data access objects (all DB queries go here)
   - `app/models/` — SQLAlchemy ORM models
   - `app/schemas/` — Pydantic models for request/response
   - `app/enums/` — StrEnum definitions
   - `app/core/` — Config, database, exceptions, centralized logging
   - `app/utils/` — Shared utilities

   ### Frontend (client/)
   - `src/components/ui/` — shadcn primitives
   - `src/components/shared/` — Shared app components
   - `src/features/` — Feature compositions
   - `src/pages/` — Route-level pages
   - `src/services/` — API service classes
   - `src/hooks/queries/` — React Query hooks
   - `src/types/` — TypeScript interfaces and enums
   - `src/contexts/` — React contexts
   - `src/styles/` — Design tokens and globals

   ### Documentation (docs/)
   - Updated before every push via git hook
   - Contains architecture, API, deployment, and development docs

   ## Logging

   - **Single logging configuration** in `app/core/logging.py` — all modules use `get_logger(__name__)`.
   - Never use `import logging` directly or configure logging anywhere else.
   - Every log line includes `correlation_id` (traces a full request) and `tenant_id` (multi-tenant context).
   - Logs write to `logs/app.log` (10 MB max, then deleted and restarted — no rotated copies) and stdout.
   - A FastAPI middleware sets `correlation_id` and `tenant_id` via context vars on every request.

   ## Commands

   All commands use `just`. **All `run` and `test` commands auto-detect available ports** — if the default port (8000 for backend, 5173 for frontend) is busy, the next available port is used automatically. This allows multiple instances to run side by side without collisions.

   - `just init` — Install all dependencies and set up the project
   - `just run` — Start the full stack with hot reload (auto-finds ports, prints URLs)
   - `just test-smoke` — Run smoke tests (auto-finds ports)
   - `just test-e2e` — Spin up test servers on available ports and run E2E tests
   - `just test-e2e-file <file>` — Run a specific E2E test file
   - `just test-e2e-grep <pattern>` — Run E2E tests matching a pattern
   - `just test-servers` — Start test servers on available ports (for manual E2E runs)
   - `just test-integration` — Run integration tests (frontend)
   - `just test-backend` — Run all backend tests (auto-finds port)
   - `just test-backend-file <file>` — Run a specific backend test file
   - `just test-backend-grep <pattern>` — Run backend tests matching a pattern
   - `just test-frontend` — Run all frontend tests
   - `just lint` — Run linters for both backend and frontend
   - `just db-migrate <message>` — Create a new Alembic migration
   - `just db-upgrade` — Apply database migrations

   ## ⚠️ Git Hooks — Verify on Every Session

   This project uses git hooks in `.githooks/` for smoke tests and automated code review on push.

   **At the start of every conversation**, verify that git hooks are properly configured:

   1. Run: `git config core.hooksPath`
   2. If the output is `.githooks` — hooks are enabled, proceed normally.
   3. If the output is empty or anything else — hooks are NOT enabled. **Immediately alert the user**:
      - Tell them: "Git hooks are not configured. The pre-push hook (smoke tests + code review) will not run."
      - Ask them to run: `just setup-hooks`
      - Do NOT proceed with any work until the user confirms hooks are enabled.

   Hooks are critical — they run smoke tests and Claude code review before every push. Without them, broken code can be pushed.

   ## Data Flow

   ```
   Router → Service → DAO → Database
   ```
   - Routers handle HTTP, call services
   - Services contain business logic, call DAOs
   - DAOs execute queries, return Pydantic models
   - No layer skipping allowed
   ```

6. **`AGENTS.md`** — Create as a symlink to `CLAUDE.md`:
   ```bash
   ln -s CLAUDE.md AGENTS.md
   ```

### Phase 6: Justfile

Create the `justfile` with all commands:

```just
# Default port preferences (overridden automatically if busy)
DEFAULT_BACKEND_PORT := "8000"
DEFAULT_FRONTEND_PORT := "5173"

# Default: list available commands
default:
    @just --list

# Find an available port starting from a preferred port.
# Usage: just _find-port 8000
# Returns an available port number on stdout.
[private]
_find-port PREFERRED:
    #!/usr/bin/env bash
    port={{ PREFERRED }}
    while lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; do
        echo "Port $port is busy, trying next..." >&2
        port=$((port + 1))
    done
    echo "$port"

# Initialize the project: install all dependencies and set up the database
init:
    @echo "Installing backend dependencies..."
    cd backend && uv sync --all-extras
    @echo "Installing frontend dependencies..."
    cd client && npm install
    @echo "Installing Playwright browsers..."
    cd client && npx playwright install --with-deps
    @echo "Starting database..."
    docker compose up -d
    @echo "Waiting for database to be ready..."
    sleep 3
    @echo "Running database migrations..."
    cd backend && uv run alembic upgrade head
    @echo "Project initialized successfully."

# Run the full stack with hot reload (auto-finds available ports)
run:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT

    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    FRONTEND_PORT=$(just _find-port {{ DEFAULT_FRONTEND_PORT }})

    echo "=== Starting backend on port $BACKEND_PORT ==="
    cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port "$BACKEND_PORT" &

    echo "=== Starting frontend on port $FRONTEND_PORT (proxying to backend:$BACKEND_PORT) ==="
    cd client && VITE_BACKEND_PORT="$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" &

    echo ""
    echo "=== Stack running ==="
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend:  http://localhost:$BACKEND_PORT"
    echo "  API docs: http://localhost:$BACKEND_PORT/docs"
    echo ""
    wait

# Run smoke tests (auto-finds available ports for test servers)
test-smoke:
    #!/usr/bin/env bash
    set -euo pipefail
    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    echo "=== Running backend smoke tests (port $BACKEND_PORT) ==="
    cd backend && TEST_PORT="$BACKEND_PORT" uv run pytest tests/ -m smoke --tb=short -q
    echo "=== Running frontend smoke tests ==="
    cd client && npm run test -- --run tests/smoke

# Start test servers (backend + frontend) on available ports for E2E tests
test-servers:
    #!/usr/bin/env bash
    set -euo pipefail
    trap 'kill 0' EXIT

    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    FRONTEND_PORT=$(just _find-port {{ DEFAULT_FRONTEND_PORT }})

    echo "=== Starting test backend on port $BACKEND_PORT ==="
    cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &

    echo "=== Starting test frontend on port $FRONTEND_PORT (proxying to backend:$BACKEND_PORT) ==="
    cd client && VITE_BACKEND_PORT="$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" &

    echo ""
    echo "=== Test servers running ==="
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
    echo "  Backend:  http://localhost:$BACKEND_PORT"
    echo ""

    # Write ports to a temp file so test-e2e can read them
    echo "BACKEND_PORT=$BACKEND_PORT" > .test-ports
    echo "FRONTEND_PORT=$FRONTEND_PORT" >> .test-ports
    wait

# Run end-to-end tests (auto-finds available ports)
test-e2e *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    FRONTEND_PORT=$(just _find-port {{ DEFAULT_FRONTEND_PORT }})
    trap 'kill 0' EXIT

    echo "=== Starting test servers (backend:$BACKEND_PORT, frontend:$FRONTEND_PORT) ==="
    cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT" &
    cd client && VITE_BACKEND_PORT="$BACKEND_PORT" npx vite --port "$FRONTEND_PORT" &
    sleep 3

    echo "=== Running E2E tests ==="
    cd client && BASE_URL="http://localhost:$FRONTEND_PORT" npx playwright test {{ ARGS }}

# Run a specific e2e test file
test-e2e-file FILE:
    just test-e2e {{ FILE }}

# Run e2e tests matching a pattern
test-e2e-grep PATTERN:
    just test-e2e --grep "{{ PATTERN }}"

# Run frontend integration tests
test-integration:
    cd client && npm run test -- --run tests/integration

# Run all backend tests (auto-finds available port for test server)
test-backend *ARGS:
    #!/usr/bin/env bash
    set -euo pipefail
    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    echo "=== Running backend tests (port $BACKEND_PORT) ==="
    cd backend && TEST_PORT="$BACKEND_PORT" uv run pytest tests/ {{ ARGS }}

# Run a specific backend test file
test-backend-file FILE:
    #!/usr/bin/env bash
    set -euo pipefail
    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    cd backend && TEST_PORT="$BACKEND_PORT" uv run pytest {{ FILE }} -v

# Run backend tests matching a pattern
test-backend-grep PATTERN:
    #!/usr/bin/env bash
    set -euo pipefail
    BACKEND_PORT=$(just _find-port {{ DEFAULT_BACKEND_PORT }})
    cd backend && TEST_PORT="$BACKEND_PORT" uv run pytest -k "{{ PATTERN }}" -v

# Run all frontend tests (integration + unit)
test-frontend:
    cd client && npm run test -- --run

# Lint both backend and frontend
lint:
    cd backend && uv run ruff check .
    cd client && npm run lint

# Format code
format:
    cd backend && uv run ruff format .
    cd client && npm run format

# Create a new database migration
db-migrate MESSAGE:
    cd backend && uv run alembic revision --autogenerate -m "{{ MESSAGE }}"

# Apply database migrations
db-upgrade:
    cd backend && uv run alembic upgrade head

# Rollback last database migration
db-downgrade:
    cd backend && uv run alembic downgrade -1

# Start the database
db-start:
    docker compose up -d

# Stop the database
db-stop:
    docker compose down

# Reset the database (destructive)
db-reset:
    docker compose down -v
    docker compose up -d
    sleep 3
    cd backend && uv run alembic upgrade head
```

### Phase 7: Git Hooks

Initialize git and set up two pre-push hooks. Both hooks run on every push.

1. **Initialize git**:
   ```bash
   cd <project-name>
   git init
   ```

2. **Create `.githooks/` directory** (project-local hooks, tracked in git):
   ```bash
   mkdir -p .githooks
   ```

3. **Configure git to use project hooks**:
   ```bash
   git config core.hooksPath .githooks
   ```

4. **Create `.githooks/pre-push`**:

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail

   echo "=== Pre-push hook: Running smoke tests ==="
   just test-smoke
   SMOKE_EXIT=$?

   if [ $SMOKE_EXIT -ne 0 ]; then
       echo "Smoke tests failed. Push aborted."
       exit 1
   fi

   echo ""
   echo "=== Pre-push hook: Claude review & doc update ==="
   # Get the range of commits being pushed
   while read local_ref local_oid remote_ref remote_oid; do
       if [ "$remote_oid" = "0000000000000000000000000000000000000000" ]; then
           # New branch — review all commits
           RANGE="$local_oid"
       else
           RANGE="$remote_oid..$local_oid"
       fi
   done

   # Run Claude to review changes and update docs
   claude --print --dangerously-skip-permissions \
       "You are running as a pre-push git hook. Do the following two tasks:

   1. **Code Review**: Review the changes in this push (commits: ${RANGE:-HEAD~1..HEAD}).
      Run a quick review of the diff. If you find any blockers (security issues, broken logic, missing error handling), output them clearly and exit with a non-zero code.

   2. **Update Documentation**: Based on the changes in this push, update the docs/ folder:
      - If new endpoints were added, update docs/api.md
      - If architecture changed, update docs/architecture.md
      - If setup steps changed, update docs/development.md
      - If the stack or main components changed, update CLAUDE.md
      - Only update files that are actually affected by the changes
      - Stage and amend the last commit with any doc changes

   Review the diff with: git diff ${RANGE:-HEAD~1..HEAD}
   Changed files: git diff --name-only ${RANGE:-HEAD~1..HEAD}"

   echo "=== Pre-push hook complete ==="
   ```

5. **Make the hook executable**:
   ```bash
   chmod +x .githooks/pre-push
   ```

6. **Add hook path config to `just init`** — The `just init` recipe already handles this, but also add to the justfile:
   ```just
   # Configure git hooks
   setup-hooks:
       git config core.hooksPath .githooks
       chmod +x .githooks/pre-push
       @echo "Git hooks configured."
   ```

   Update `just init` to include `just setup-hooks`.

### Phase 8: Gitignore

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
*.egg

# Node
node_modules/
dist/

# Environment
.env
.env.local
.env.*.local

# IDE
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Testing
coverage/
htmlcov/
.pytest_cache/
.coverage
test-results/
playwright-report/

# Database
*.db
*.sqlite3

# Logs
logs/

# Runtime
.test-ports

# Build
*.log
```

### Phase 9: Initial Commit & Verification

1. Run `just init` to install all dependencies.
2. Verify the backend starts: `cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000` — confirm health endpoint responds.
3. Verify the frontend starts: `cd client && npm run dev` — confirm it loads in the browser.
4. Run `just lint` to verify no lint errors.
5. Create the initial commit:
   ```bash
   git add .
   git commit -m "Initial project scaffold: FastAPI + React + shadcn + Postgres"
   ```
6. **CHECKPOINT**: Report to the user that the project is set up, list the available `just` commands, and confirm the stack is running.

## Post-Setup Notes

- The `docs/` folder is automatically kept up to date by the pre-push git hook via Claude.
- Smoke tests run on every push — if they fail, the push is blocked.
- Claude reviews every push for blockers and updates documentation accordingly.
- `AGENTS.md` is a symlink to `CLAUDE.md` — edit `CLAUDE.md` and both stay in sync.
- **Ports are auto-assigned**: default is 8000 (backend) and 5173 (frontend), but if busy the next available port is used. The assigned ports are printed at startup. This allows multiple instances (dev + test, or multiple devs) to run simultaneously without collisions.
- Use `just run` to start the full stack with hot reload during development.
- Use `just test-servers` to start test servers on separate available ports for manual E2E testing.
- Use `just init` after cloning to set up the project on a new machine.
