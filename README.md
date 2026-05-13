# quick-launch `ql`

One command to clone any git project and run it in a Docker sandbox.

```
ql launch https://github.com/user/myproject
```

What happens:
1. **Access check** — detects GitHub / Bitbucket / GitFlic, finds your token or SSH key
2. **Clone** — clones into `sandboxes/myproject/`
3. **README** — renders the project README in your terminal
4. **Env** — reads `.env.example`, creates `.env`, highlights auth params
5. **Sandbox** — runs `docker compose up --build -d`

## Install

```bash
git clone https://github.com/elementary1997/quick_launch
cd quick_launch
python -m venv .venv && source .venv/bin/activate
pip install -e .
ql --help
```

## Credentials

Place your tokens in the `keys/` folder (gitignored) or set env vars:

| Provider  | Env var | File |
|-----------|---------|------|
| GitHub    | `GITHUB_TOKEN` | `keys/github.token` |
| Bitbucket | `BITBUCKET_USER` + `BITBUCKET_APP_PASSWORD` | `keys/bitbucket.{user,token}` |
| GitFlic   | `GITFLIC_TOKEN` | `keys/gitflic.token` |

SSH keys: `keys/github_rsa`, `keys/bitbucket_rsa`, `keys/gitflic_rsa`

## Commands

```
ql launch <url>              Full pipeline
ql launch <url> --no-sandbox Skip docker-compose
ql launch <url> --fg         Attach to compose logs
ql down   <url|name>         Stop sandbox
ql status <url|name>         Show container status
ql keys                      Show credential hints
```

## Requirements

- Python 3.10+
- Docker with Compose v2 (`docker compose`)
- Git
