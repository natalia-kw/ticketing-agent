# Ticketing Agent

A mock support ticketing API, an AI agent that manages tickets through it, an MCP server exposing the same tools, an LLM pull request review bot, and a Terraform skeleton for running the API on Azure.

| Part | What it is | Where |
|---|---|---|
| 1 | Mock ticketing API (FastAPI, in-memory) | `api/` |
| 2 | GenAI agent with a CLI (Azure OpenAI tool calling) | `agent/` |
| Bonus | MCP server exposing the API as tools, used by the agent with `--mcp` | `mcp_server/`, `agent/mcp_tools.py` |
| 3 | PR review bot running in GitHub Actions | `scripts/analyze_pr.py`, `.github/workflows/pr-review.yml` |
| 4 | Terraform skeleton for Azure App Service | `infra/` |
| 5 | Design decision I would change in production | [Part 5](#part-5-what-i-would-change-in-production) |

Everything was developed and tested on Windows with Python 3.12, and CI runs on Linux.

---

## Requirements

- **Python 3.12**
- **Git**
- **Azure OpenAI credentials** (endpoint, API key, API version, deployment name) for the agent
- **Terraform 1.6 or newer**, only for Part 4

## Setup

All commands are run from the repository root.

**1. Clone the repository**

```bash
git clone https://github.com/natalia-kw/ticketing-agent.git
cd ticketing-agent
```

**2. Create and activate a virtual environment**

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

If PowerShell says running scripts is disabled, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Create the settings file**

Windows (PowerShell):

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

Open `.env` and fill in the four Azure OpenAI values. The deployment name is the "model" value provided with the assessment.

| Setting | Meaning |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Base URL of the Azure OpenAI resource, for example `https://<name>.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | API key |
| `AZURE_OPENAI_API_VERSION` | API version |
| `AZURE_OPENAI_DEPLOYMENT` | Deployment (model) name |
| `TICKET_API_URL` | Where the agent finds the API. Default `http://localhost:8000` |
| `SEED_DATA` | `true` starts the API with 10 example tickets, `false` starts it empty |

`.env` is listed in `.gitignore` and is never committed.

---

## Part 1: Mock Ticketing API

**Start the API:**

```bash
uvicorn api.main:app --reload
```

Then open **http://localhost:8000/docs** for interactive documentation where every endpoint can be tried in the browser.

### Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/tickets` | List tickets. Optional filters: `status` and `q` (keyword in title or description), which can be combined |
| GET | `/tickets/{id}` | Get one ticket |
| POST | `/tickets` | Create a ticket (always starts as `OPEN`) |
| PATCH | `/tickets/{id}` | Update only the fields sent |
| DELETE | `/tickets/{id}` | Delete a ticket |
| POST | `/tickets/{id}/comments` | Add a comment |
| GET | `/health` | Health check |

Each ticket has `id`, `title`, `description`, `created`, `status` (`OPEN`, `RESOLVED`, `CLOSED`), `resolution`, and the optional `comments` and `updated_at`.

### Business errors

Every error returns a readable message in the same format: `{"detail": "..."}`.

| Case | Status | Example message |
|---|---|---|
| Ticket ID does not exist (required) | 404 | `Ticket 999 not found.` |
| Invalid status (required) | 422 | `Invalid status 'PROGRESS'. Valid values are: OPEN, RESOLVED, CLOSED.` |
| RESOLVED without a resolution note (optional) | 422 | `A resolution note is required when setting status to RESOLVED. ...` |
| Empty title, unknown field, wrong type | 422 | `Unknown field 'priority' is not allowed.` |

### Notes

- Tickets are stored in memory, so **every restart resets the data** to the 10 seed tickets. With `--reload`, the API also restarts whenever a project file changes.
- The seed tickets are made-up IT issues with no personal data.

---

## Part 2: The Agent

The API must be running. Open a **second terminal**, activate the virtual environment there as well, and start the agent:

```bash
python -m agent.cli
```

Each tool call is printed as it happens (for example `[tool] update_ticket({"ticket_id":1,"status":"PROGRESS"})`), so you can follow how the agent chains tools. Type `reset` to start a new conversation and `exit` to quit.

| Option | Effect |
|---|---|
| `--quiet` | Hide tool calls |
| `--mcp` | Get the tools from the MCP server instead of calling the API directly (see the bonus section) |

### Scenarios from the brief

Run these in order with freshly started API data. Ticket `1` is a valid ID and `999` does not exist.

| Message | Expected behavior |
|---|---|
| `Create a new ticket about a keyboard not working.` | Creates ticket #11 with a title and description |
| `Retrieve all open tickets.` | Lists open tickets using the status filter |
| `Get details for ticket 1.` | Shows ticket #1 |
| `Update ticket 1 to have the status 'PROGRESS'.` | Sends the status to the API, receives the 422, explains that PROGRESS is invalid and lists OPEN, RESOLVED and CLOSED from the API's message |
| `Update ticket 1 to be RESOLVED, adding 'Replaced faulty cable' as the resolution.` | Updates status and resolution in one call |
| `Update ticket 999 to 'CLOSED'.` | Receives the 404 and reports that the ticket does not exist |

A few more that show orchestration and judgment:

| Message | Expected behavior |
|---|---|
| `Close the printer ticket.` | Searches for "printer", finds #2, then closes it (two chained tools) |
| `Resolve ticket 4.` | Asks for a resolution note instead of inventing one |
| `Delete ticket 6.` | Asks for confirmation before deleting |

### How it works

1. The conversation and the tool definitions are sent to Azure OpenAI (Chat Completions with function calling).
2. If the model requests tools, the agent runs them against the API and sends the results back.
3. This repeats until the model replies in text, with a limit of 8 tool rounds per message.

Design choices behind the error handling:

- **The API client never raises on 4xx.** Every call returns `{"ok": false, "status_code": 422, "error": "<the API's message>"}`, and this is exactly what the model receives. If the API is not running, the result says so and explains how to start it.
- **The API is the single source of truth for business rules.** The `status` tool parameter is free text on purpose, so an invalid value like PROGRESS reaches the API and the agent relays the API's own message with the valid options.
- **The system prompt** (`agent/prompts.py`) tells the model how to turn each kind of error into actionable feedback, never to invent a resolution note, and to confirm before deleting.
- **The provided model only supports function tools on Chat Completions with `reasoning_effort="none"`**, so the agent sets it explicitly.

### Code layout

| File | Responsibility |
|---|---|
| `agent/llm.py` | Azure OpenAI client from `.env`, with a clear message if a setting is missing |
| `agent/api_client.py` | HTTP client for the API, returns structured results instead of raising |
| `agent/tools.py` | Tool definitions and the executor for direct mode |
| `agent/prompts.py` | System prompt |
| `agent/agent.py` | The agent loop, independent of where the tools come from |
| `agent/cli.py` | Command-line interface |

---

## Bonus: MCP Server

`mcp_server/server.py` exposes the six ticket operations as MCP tools using the official MCP Python SDK (v2). The tools reuse `agent/api_client.py`, so there is no duplicated API logic.

**Use it from the agent** (API running in another terminal):

```bash
python -m agent.cli --mcp
```

The agent starts the MCP server as a subprocess, discovers the tools from it, and sends every tool call through it. The agent loop itself does not change.

API errors keep their meaning across MCP: the server reports them as tool errors (`is_error`) with the status code and the API's message, and the agent converts them back into the same format as direct mode. The model therefore receives identical information in both modes.

**Use it from another MCP host** (for example Claude Desktop), with the API running:

```json
{
  "mcpServers": {
    "ticketing": {
      "command": "<path to the repository>/.venv/Scripts/python.exe",
      "args": ["-m", "mcp_server.server"],
      "env": {
        "PYTHONPATH": "<path to the repository>",
        "TICKET_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

On macOS / Linux the Python path is `.venv/bin/python`.

---

## Tests

```bash
pytest -v
```

46 tests, none of which need Azure credentials or a running server:

- **API:** every endpoint, both filters and their combination, and every error case.
- **API client:** success, 404, 422 and an unreachable API.
- **Agent:** runs with a scripted fake model against the real API in memory. Covers errors reaching the model, chaining search and update, conversation history, the tool round limit, and recovery when the model call fails.
- **MCP server:** connected in memory. Covers tool discovery and that status codes and messages survive the MCP round trip.
- **PR bot:** diff truncation and finding its earlier comment.

Linting and formatting use Ruff:

```bash
ruff format --check .
ruff check .
```

---

## CI/CD

### CI (`.github/workflows/ci.yml`)

Runs on every push to `main` and on every pull request, with two parallel jobs:

- **Lint and test:** installs dependencies, checks formatting, lints and runs all tests.
- **Terraform validate:** `terraform fmt -check`, `terraform init -backend=false` and `terraform validate` in `infra/`.

The workflow has read-only permissions and needs no secrets.

### Part 3: PR review bot (`.github/workflows/pr-review.yml`)

Triggers when a pull request is **opened** or **synchronized** (new commits pushed). It runs `scripts/analyze_pr.py`, which:

1. Fetches the pull request diff from the GitHub API.
2. Sends it to Azure OpenAI for a summary and improvement suggestions.
3. Posts **one comment** on the pull request. On later pushes it updates that same comment instead of adding new ones.

**See it in action:** [pull request #1](https://github.com/natalia-kw/ticketing-agent/pull/1) added the Terraform skeleton. The bot reviewed it when it was opened, and updated its comment after a second commit applied two of its suggestions.

Details:

- Azure credentials are stored as **repository secrets**. GitHub access uses the built-in `GITHUB_TOKEN` with only `contents: read` and `pull-requests: write`.
- Very large diffs are shortened to 60,000 characters, and the comment says so.
- If a pull request is updated while a review is still running, the older run is cancelled.
- **Pull requests from forks are skipped**, because GitHub does not give secrets to them.

**To run the bot in your own copy:** add `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION` and `AZURE_OPENAI_DEPLOYMENT` as repository secrets (Settings > Secrets and variables > Actions), then open a pull request from a branch in the same repository. With the GitHub CLI, `gh secret set -f .env` sets them from your `.env` file.

---

## Part 4: Terraform

```bash
cd infra
terraform init
terraform validate
```

Expected result: `Success! The configuration is valid.`

Three resources describe how the API would run on Azure:

| Resource | Purpose |
|---|---|
| `azurerm_resource_group` | Holds all resources |
| `azurerm_service_plan` | Linux compute for the app |
| `azurerm_linux_web_app` | Runs the API on Python 3.12 with uvicorn, HTTPS only, using `/health` as the health check |

| Variable | Default | Purpose |
|---|---|---|
| `app_name` | `ticketing-api` | Base name for all resources, validated against Azure naming rules |
| `location` | `swedencentral` | Azure region |
| `sku_name` | `B1` | App Service plan size |
| `subscription_id` | none | Required for `plan` and `apply`, not for `validate` |

Outputs: `api_url`, `api_docs_url` and `resource_group_name`.

Nothing is deployed. To deploy, you would run `terraform plan -var="subscription_id=<your subscription>"`, choose a globally unique `app_name`, and deploy the code to the web app. As the brief requested, there is no networking, storage account or Key Vault.

---

## Part 5: What I would change in production

**I would replace the in-memory storage with PostgreSQL.**

The in-memory dictionary was the right choice for a mock API that has to run anywhere with no setup, but it breaks down in production in three ways:

1. **Data is lost on every restart and deployment.** Azure App Service restarts apps during deployments, scaling and platform maintenance, and every restart would wipe all tickets.
2. **It does not work with more than one instance.** The Terraform setup runs the API on App Service, which can scale out to several instances. Each instance would have its own separate dictionary, so a ticket created on one instance would be missing on another, and users would see different data depending on which instance handled their request.
3. **It is not safe under concurrent writes.** Two simultaneous updates to the same ticket could overwrite each other without either request noticing.

PostgreSQL solves all three: data is persistent, every instance shares one database, and transactions keep concurrent updates consistent. The current design already prepares for this. All storage goes through the `TicketRepository` class, so moving to PostgreSQL means writing a PostgreSQL version of that one class, while the endpoints, the business rules, the agent and the MCP server stay unchanged. In Terraform it would add an Azure Database for PostgreSQL Flexible Server, with the connection string kept in Key Vault.

Other changes I would make, briefly:

- **Authentication** on the API and the MCP server.
- **Remote Terraform state** in an Azure Storage account, so the state is shared and locked.
- **One source of tool definitions:** the MCP server would be the only place tools are defined, instead of also in `agent/tools.py`.
- **Give the agent the valid values upfront** (for example from the API's OpenAPI schema) to avoid a wasted call, while keeping the API as the final check.

---

## Project structure

```
api/                  Mock ticketing API (Part 1)
  main.py             Endpoints and error handling
  models.py           Data models and validation
  repository.py       In-memory storage and business rules
  seed_data.json      Example tickets
agent/                AI agent (Part 2)
  cli.py              Command-line interface
  agent.py            Agent loop
  tools.py            Tool definitions for direct mode
  mcp_tools.py        Tool runner for MCP mode
  api_client.py       HTTP client for the API
  llm.py              Azure OpenAI client
  prompts.py          System prompt
mcp_server/server.py  MCP server (bonus)
scripts/analyze_pr.py PR review bot (Part 3)
infra/                Terraform skeleton (Part 4)
tests/                Test suite
.github/workflows/    CI and PR review workflows
```