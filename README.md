# quick-launch `ql`

Один командой клонируй любой git-репозиторий и запускай его в Docker-песочнице.

```
ql launch https://github.com/user/myproject
```

## Что происходит

1. **Проверка доступа** — определяет провайдер (GitHub / GitLab / Bitbucket / GitFlic), ищет токен или SSH-ключ. Если не найден — спрашивает интерактивно
2. **Клонирование** — клонирует в `sandboxes/myproject/` (или делает `pull`, если уже есть)
3. **README** — рендерит README проекта прямо в терминале
4. **Окружение** — читает `.env.example`, создаёт `.env` с дефолтами, выводит таблицу с auth-параметрами
5. **Песочница** — запускает `docker compose up --build -d`

## Установка

```bash
git clone https://github.com/elementary1997/quick_launch
cd quick_launch
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
ql --help
```

## Учётные данные

Токены хранятся в папке `keys/` (в `.gitignore`) или передаются через переменные окружения:

| Провайдер | Переменная окружения | Файл |
|-----------|----------------------|------|
| GitHub    | `GITHUB_TOKEN`       | `keys/github.token` |
| GitLab    | `GITLAB_TOKEN`       | `keys/gitlab.token` |
| Bitbucket | `BITBUCKET_USER` + `BITBUCKET_APP_PASSWORD` | `keys/bitbucket.{user,token}` |
| GitFlic   | `GITFLIC_TOKEN`      | `keys/gitflic.token` |

SSH-ключи: `keys/github_rsa`, `keys/gitlab_rsa`, `keys/bitbucket_rsa`, `keys/gitflic_rsa`

Пути можно переопределить через переменные окружения:
```bash
export QL_KEYS_DIR=/home/user/.ql/keys
export QL_SANDBOXES_DIR=/home/user/.ql/sandboxes
```

## Команды

```
ql launch <url>              Полный пайплайн: клон → env → sandbox
ql launch <url> --no-sandbox Пропустить docker-compose
ql launch <url> --fg         Прикрепиться к выводу compose
ql list                      Показать все локальные sandbox'ы
ql down   <url|name>         Остановить sandbox
ql status <url|name>         Статус контейнеров
ql keys                      Подсказки по настройке учётных данных
```

## Требования

- Python 3.10+
- Docker с Compose v2 (`docker compose`)
- Git
