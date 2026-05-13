# LLM Gateway Secrets Manager

This repository is now structured so you can keep it in Git as a shared Python library and use it from all of your local projects.

The library stores secrets in the system keychain through `keyring`, uses one shared service name by default, and writes masked audit logs to a shared log directory in your home folder.

## What This Gives You

- One Git repo as the source of truth
- One import path across projects: `from secrets_manager import SecretsManager`
- One shared keychain service by default: `llm_gateway`
- One shared audit log location by default: `~/.llm_gateway/logs`
- Daily log rotation with 15-day retention
- A CLI command for manually saving secrets after install
- A path to later publish the same code as a library

## Recommended Setup

The best design for your use case is:

1. Keep this repository in Git as your shared secrets library.
2. Install this library into each project's virtual environment.
3. Let every project read from the same keychain service name.
4. Keep logs in one shared home-directory location instead of inside each project.

This means every project can use the same API, and all of them can read the same stored secrets locally.

## Important Behavior Across Projects

### Secrets are shared

By default, all projects using this library read and write secrets under the same keychain service:

```python
SecretsManager.SERVICE_NAME == "llm_gateway"
```

So if one project stores the `openai` secret, another project on the same machine can read it.

### Logs are shared

By default, logs are written to:

```text
~/.llm_gateway/logs/secrets_manager.log
```

That makes the log location independent of whichever project or virtual environment imported the library.

### Each project still needs to install the library

The secret values are shared through the keychain, but Python packages are still installed per environment.  
So every local project or virtual environment that wants to use this library must install it.

## Repository Files

This repository now includes:

- `secrets_manager.py`: the reusable library module
- `save_secret.py`: CLI entry point for manually saving a secret
- `pyproject.toml`: packaging metadata so the repo can be installed locally, from Git, or published later
- `.gitignore`: excludes virtualenv, build output, and log files

## Start-to-End Setup

### 1. Keep this repo as your source of truth

Clone or keep this project in a stable local path, for example:

```bash
mkdir -p ~/projects
cd ~/projects
git clone <your-git-url> llm_gateway
```

If the repo already exists locally, commit your changes there and use that folder as the shared library source.

### 2. Commit this repository to Git

Commit this repository as your shared package codebase.  
After that, you can either:

- install it from the local path while developing it
- install it from the Git URL in other projects
- publish it later to a package registry

### 3. Install it into another local project

Activate the target project's virtual environment first, then choose one of the following approaches.

#### Option A: local editable install during development

This is the best option while you are still actively changing this library.

```bash
python -m pip install -e /absolute/path/to/llm_gateway
```

Example:

```bash
python -m pip install -e ~/projects/llm_gateway
```

With editable install:

- the target project imports `secrets_manager` directly from this repo
- code changes in this repo are immediately picked up
- you do not need to reinstall after every library code change

#### Option B: install from Git

Use this once the repo is committed and available in a remote Git server.

```bash
python -m pip install "git+https://<git-host>/<user-or-org>/<repo>.git"
```

If you use SSH:

```bash
python -m pip install "git+ssh://git@<git-host>/<user-or-org>/<repo>.git"
```

You can also pin a branch or tag:

```bash
python -m pip install "git+https://<git-host>/<user-or-org>/<repo>.git@main"
```

#### Option C: publish later and install by package name

Once published, installation becomes:

```bash
python -m pip install llm-gateway-secrets
```

## How To Make It Available To All Local Projects

For every local Python project:

1. Activate that project's virtual environment.
2. Install this library with `pip install -e /path/to/llm_gateway` or from Git.
3. Import it with `from secrets_manager import SecretsManager`.

That is the cleanest and safest setup. It avoids copying files between projects and keeps one shared implementation in Git.

## Quick Start In Another Project

After installing the library into a project, use:

```python
from secrets_manager import SecretsManager
```

Save a secret once:

```python
from secrets_manager import SecretsManager

SecretsManager.set_openai_key(
    "sk-xxxx",
    context={"app": "my-local-project", "env": "dev"},
)
```

Read it later from any other installed local project:

```python
from secrets_manager import SecretsManager

openai_key = SecretsManager.get_openai_key()

if openai_key is None:
    raise RuntimeError("OpenAI key is not available")
```

## Manual Secret Save From CLI

After the package is installed, you can use the console command:

```bash
llm-gateway-secret
```

It prompts for:

- the secret name, such as `openai`, `deepseek`, `claude`, or any custom name
- the secret value

If you are running directly from this repository without installing it yet, you can also use:

```bash
python save_secret.py
```

## Save Secrets

### Save a provider-specific API key

```python
from secrets_manager import SecretsManager

SecretsManager.set_openai_key(
    "sk-xxxx",
    context={"app": "chat-service", "env": "dev"},
)
SecretsManager.set_deepseek_key(
    "sk-deepseek-xxxx",
    context={"app": "chat-service", "request_id": "req-123"},
)
SecretsManager.set_claude_key("sk-ant-xxxx")
```

### Save any custom secret

```python
from secrets_manager import SecretsManager

SecretsManager.set_secret(
    "github",
    "ghp_xxxx",
    context={"app": "deploy-worker", "user_id": "42"},
)
SecretsManager.set_secret("database_url", "postgres://user:pass@host/db")
```

### Save by provider name dynamically

```python
from secrets_manager import SecretsManager

provider_name = "gemini"
api_key = "AIza-xxxx"

SecretsManager.set_provider_key(provider_name, api_key)
```

`set_provider_key()`, `get_provider_key()`, and `delete_provider_key()` normalize `provider_name` to lowercase before storing or reading it.

## Get Secrets

### Get the real secret for application use

```python
from secrets_manager import SecretsManager

openai_key = SecretsManager.get_openai_key()
deepseek_key = SecretsManager.get_deepseek_key()
github_token = SecretsManager.get_secret("github")
```

If a secret does not exist, the get methods return `None`.

### Get a masked value for safe display

Use `masked=True` when returning a value to logs, APIs, debug output, or UI screens:

```python
from secrets_manager import SecretsManager

masked_openai_key = SecretsManager.get_openai_key(masked=True)
masked_custom_secret = SecretsManager.get_secret(
    "github",
    masked=True,
)
```

## Delete Secrets

```python
from secrets_manager import SecretsManager

SecretsManager.delete_openai_key(
    context={"app": "chat-service", "reason": "rotation"},
)
SecretsManager.delete_secret("github")
SecretsManager.delete_provider_key("gemini")
```

## Supported Providers

Built-in helper methods are available for:

- `openai`
- `anthropic`
- `claude`
- `deepseek`
- `gemini`
- `openrouter`
- `groq`
- `mistral`
- `cohere`
- `together`
- `xai`

You can also inspect them in code:

```python
SecretsManager.SUPPORTED_PROVIDERS
```

## Logging and Audit Trail

The library automatically creates the log directory if needed and writes logs to:

```text
~/.llm_gateway/logs/secrets_manager.log
```

The active log file is rotated daily at midnight, and rotated log files are retained for 15 days. Rotated files use date-based names managed by Python logging, for example:

```text
~/.llm_gateway/logs/secrets_manager.log.2026-05-12
```

Each log entry includes:

- timestamp
- action (`set`, `get`, `delete`)
- API method used
- service name
- secret name
- masked secret value
- masked returned value
- status (`success`, `not_found`, `error`)
- caller details when detectable
- runtime details such as OS user, process id, and thread
- optional custom `context`

Raw secret values are not written to the log file.

## Caller Tracking

The library attempts to capture caller details from the Python stack, including:

- module
- function
- file
- line number

If your application has extra request metadata, pass it in `context`:

```python
from secrets_manager import SecretsManager

SecretsManager.get_openai_key(
    context={
        "app": "gateway-api",
        "request_id": "req-001",
        "user_id": "user-42",
    }
)
```

## Environment Overrides

You can keep the defaults, or override them with environment variables before importing the library:

- `LLM_GATEWAY_SERVICE_NAME`: change the keychain service name
- `LLM_GATEWAY_HOME`: change the shared home directory base
- `LLM_GATEWAY_LOG_DIR`: change only the log directory

Examples:

```bash
export LLM_GATEWAY_SERVICE_NAME="llm_gateway_team_a"
export LLM_GATEWAY_HOME="$HOME/.llm_gateway"
export LLM_GATEWAY_LOG_DIR="$HOME/.llm_gateway/logs"
```

## Packaging Notes

This repository includes a `pyproject.toml`, so it can be:

- installed from a local path
- installed directly from Git
- published later as a package

The current distribution name is:

```text
llm-gateway-secrets
```

The import name remains:

```python
from secrets_manager import SecretsManager
```

## Publish Later

When you are ready to publish this library:

1. Update the version in `pyproject.toml`.
2. Build the package:

```bash
python -m pip install --upgrade build
python -m build
```

3. You will get artifacts in `dist/`.
4. Test install from the built wheel or source archive.
5. Publish to your package index of choice.

## Generic API Summary

```python
SecretsManager.set_secret(secret_name, secret_value, context=None)
SecretsManager.get_secret(secret_name, masked=False, context=None)
SecretsManager.delete_secret(secret_name, context=None)

SecretsManager.set_provider_key(provider_name, api_key, context=None)
SecretsManager.get_provider_key(provider_name, masked=False, context=None)
SecretsManager.delete_provider_key(provider_name, context=None)
```

## Quick reference

| Topic | Command or snippet |
| --- | --- |
| Install (dev, from repo) | `python -m pip install -e /path/to/llm_gateway` |
| Install (from Git) | `python -m pip install "git+https://<host>/<org>/<repo>.git"` |
| Install (after publish) | `python -m pip install llm-gateway-secrets` |
| Import | `from secrets_manager import SecretsManager` |
| Save (generic) | `SecretsManager.set_secret("name", "value", context={...})` |
| Read (real value) | `SecretsManager.get_secret("name")` |
| Read (masked) | `SecretsManager.get_secret("name", masked=True)` |
| Delete (generic) | `SecretsManager.delete_secret("name")` |
| Save by provider string | `SecretsManager.set_provider_key("gemini", api_key)` (name lowercased) |
| Read by provider string | `SecretsManager.get_provider_key("gemini", masked=False)` |
| Delete by provider string | `SecretsManager.delete_provider_key("gemini")` |

Provider helpers follow the same pattern: `set_<provider>_key`, `get_<provider>_key`, `delete_<provider>_key` (for example `set_openai_key`, `get_openai_key`, `delete_openai_key`). Built-in names are listed in `SecretsManager.SUPPORTED_PROVIDERS`.

| Topic | Value |
| --- | --- |
| Default keychain service | `llm_gateway` (`SecretsManager.SERVICE_NAME`) |
| Default log file | `~/.llm_gateway/logs/secrets_manager.log` |
| Log rotation | Daily at midnight, keep 15 days |
| CLI (after install) | `llm-gateway-secret` |
| CLI (from repo) | `python save_secret.py` |

Environment overrides: `LLM_GATEWAY_SERVICE_NAME`, `LLM_GATEWAY_HOME`, `LLM_GATEWAY_LOG_DIR`.

Optional `context` on any `set_*`, `get_*`, or `delete_*` call is included in audit logs as structured metadata (not the secret itself).
