# Forge CI

**Forge** is a lightweight, spec-driven Continuous Integration (CI) system that builds your code in isolated Docker environments. It integrates directly with GitHub Checks and provides a CLI tool for managing projects and viewing build logs.

## 🚀 Features

* **Spec-Driven Configuration**: Define your build environment (runtime, version, commands) via a simple JSON spec.
* **Dockerized Builds**: Every CI run executes in an isolated Docker container ensuring consistency.
* **GitHub Integration**:
    * Authenticates via GitHub Apps.
    * Updates commit status with **GitHub Checks** (Pending, Success, Failure).
    * Triggered automatically via Webhooks on `git push`.
* **Real-time CLI**: Monitor build status and stream logs directly from your terminal.
* **Scalable Architecture**: Uses Redis (Upstash) for job queuing and a separate Worker process for execution.

---

## 📂 Project Structure

The project is organized as a monorepo with three main components:

```text
forge/
├── backend/       # FastAPI server (API, Webhooks, DB Models)
├── worker/        # Background worker (Consumes Redis queue, runs Docker)
├── cli/           # "forge" CLI tool (Typer-based)
├── shared/        # Shared utilities (GitHub Auth, etc.)
└── docker-compose.yml (Optional/Suggested)
```

---

## 🛠️ Prerequisites

* **Python 3.9+**
* **Docker** (Must be running on the host machine for the Worker)
* **PostgreSQL** (Database)
* **Redis** (Job Queue - e.g., Upstash)
* **GitHub App** (Created in your GitHub Developer settings)

---

## ⚙️ Installation & Setup

### 1. Environment Configuration

Create a `.env` file in the root (or ensure these variables are available to both Backend and Worker):

```env
# Database & Queue
DATABASE_URL=postgresql://user:pass@localhost:5432/forge_db
REDIS_URL=redis://default:pass@...upstash.io:6379

# GitHub App Configuration
GITHUB_APP_ID=123456
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY----- ... "
GITHUB_WEBHOOK_SECRET=your_webhook_secret
```

### 2. Backend Service

The backend handles API requests and receives GitHub webhooks.

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
*Server runs on `http://localhost:8000`*

### 3. Worker Service

The worker consumes jobs from Redis, clones repos, and runs Docker commands.

```bash
cd worker
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Add root to python path to import 'shared' modules
export PYTHONPATH=$PYTHONPATH:$(pwd)/..
python worker.py
```

### 4. CLI Tool

Install the `forge` CLI globally or in a virtual environment to interact with the system.

```bash
cd cli
pip install -e .
```

---

## 📖 Usage Guide

### 1. Create a Project
*(Currently done via API, e.g., Postman or Curl)*

Send a `POST /projects` request to the backend with your build spec:

```json
{
  "name": "My Next.js App",
  "spec": {
    "runtime": "node",
    "runtime_version": "20",
    "framework": "nextjs",
    "tool": "next",
    "commands": {
      "install": "npm install",
      "build": "npm run build",
      "test": "npm run test"
    }
  }
}
```
**Response:** Returns a `project_id` (e.g., `proj_a1b2c3d4`).

### 2. Link Repository

Navigate to your local git repository and initialize Forge.

```bash
cd /path/to/my-repo
forge init
# Output: ✅ forge initialized
```

Link your local repo to the remote Forge project ID:

```bash
forge link proj_a1b2c3d4
# Output: 🔗 Repo linked successfully
```

### 3. Trigger a Build

Simply push code to GitHub. The webhook will trigger the worker.

```bash
git add .
git commit -m "feat: updated navbar"
git push origin main
```

### 4. Monitor Status

Check the build status from your terminal:

```bash
forge status
```

### 5. View Logs

View the logs of the latest run (or specify a run index):

```bash
forge logs
```

---

## 🏗️ Architecture Details

### The Build Spec
The core of Forge is the **Project Spec**. This JSON object tells the worker how to configure the Docker container.
* **Runtime**: Currently supports `node` and `python`.
* **Commands**:
    * `install`: Runs first (e.g., `npm install`).
    * `build` / `test`: Runs combined (e.g., `npm install && npm run build`).

### The Worker Pipeline
1.  **Dequeues Job**: Reads `ci_jobs` from Redis.
2.  **Report Status**: Calls GitHub API to set check status to `in_progress`.
3.  **Prepare Workspace**: Creates a temporary directory.
4.  **Clone**: `git clone` the repository.
5.  **Checkout**: `git checkout` the specific commit SHA.
6.  **Execute**: Spins up a Docker container (e.g., `node:20`) mounting the workspace.
7.  **Finalize**: Updates DB with logs and sets GitHub check to `success` or `failure`.

---

## 🛡️ Security & Notes

* **Secrets**: Ensure `private.pem` and `.env` files are in your `.gitignore`.
* **Docker Socket**: The worker requires access to the host's Docker socket to spawn sibling containers.
* **Validation**: Webhooks are verified using HMAC SHA-256 signatures.