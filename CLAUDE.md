# quick-launch

CLI tool (`ql`) to clone any git repo and spin it up in a Docker Compose sandbox in one command.

## What it does

1. Detects the git provider (GitHub, Bitbucket, GitFlic) from the URL
2. Checks for stored credentials (token file, env var, or SSH key)
3. Clones or pulls the repo into `sandboxes/<repo-name>/`
4. Displays the README
5. Reads `.env.example` → creates `.env` with defaults → shows all auth-related vars in a table
6. Runs `docker compose up --build -d`

## Project layout

```
quick_launch/           # Python package
  cli.py                # Typer CLI entry point  (commands: launch, down, status, list, keys)
  config.py             # Centralized paths: KEYS_DIR, SANDBOXES_DIR (overridable via env vars)
  credentials.py        # Interactive token prompt — ask & optionally save to keys/
  providers/            # One module per git host
    base.py             # Abstract Provider + CloneResult (has_auth flag)
    github.py
    gitlab.py
    bitbucket.py
    gitflic.py
  cloner.py             # git clone / pull via GitPython
  readme.py             # Find and render README with Rich
  env_manager.py        # .env discovery, defaults, auth-param table
  sandbox.py            # docker compose up/down/status/find_compose
keys/                   # Credential files (gitignored)
sandboxes/              # Cloned repos (gitignored)
```

## Dev setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"   # or: pip install -e .
ql --help
```

## Adding a new provider

1. Create `quick_launch/providers/<name>.py` subclassing `Provider`
2. Implement `matches(url)`, `check_access(keys_dir)`, `credential_hint()`
3. Set `has_auth=True` in `CloneResult` when a real credential is found
4. Register in `quick_launch/providers/__init__.py` → `PROVIDERS` list
5. Add token filename to `_TOKEN_FILES` dict in `cli.py` for interactive prompt

## Credential lookup order (per provider)

| Provider  | Env var                              | File               | SSH key           |
|-----------|--------------------------------------|--------------------|-------------------|
| GitHub    | `GITHUB_TOKEN`                       | `keys/github.token`| `keys/github_rsa` |
| GitLab    | `GITLAB_TOKEN`                       | `keys/gitlab.token`| `keys/gitlab_rsa` |
| Bitbucket | `BITBUCKET_USER` + `BITBUCKET_APP_PASSWORD` | `keys/bitbucket.{user,token}` | `keys/bitbucket_rsa` |
| GitFlic   | `GITFLIC_TOKEN`                      | `keys/gitflic.token`| `keys/gitflic_rsa`|

## Path overrides

```bash
export QL_KEYS_DIR=/home/user/.ql/keys
export QL_SANDBOXES_DIR=/home/user/.ql/sandboxes
```

## Sandbox directory

Each cloned project lives in `sandboxes/<repo-name>/`. The tool reads the first
`docker-compose.yml / yaml` or `compose.yml / yaml` found in the repo root.

## Commands

```
ql launch <url>              # full pipeline
ql launch <url> --no-sandbox # skip docker-compose
ql launch <url> --fg         # attach to compose output
ql list                      # show all local sandboxes
ql down   <url|name>         # docker compose down
ql status <url|name>         # docker compose ps
ql keys                      # show credential hints
```

## Conventions

- No comments unless the WHY is non-obvious
- No backwards-compat shims — delete unused code
- Rich for all terminal output; no bare `print()`
- Providers never print; they return data — CLI layer prints
