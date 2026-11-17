# Дүкен кассасы және қойма есебі — Backend API

Django + Django REST Framework + PostgreSQL негізіндегі API: POS касса, жеткізушіден қабылдау,
есептен шығару, түгендеу, құжаттар журналы және есептер. Пайдаланушы интерфейсі — бөлек репо:
[`DevUMRA/kassa-template-frontend-angular`](https://github.com/DevUMRA/kassa-template-frontend-angular).

- API құжаттамасы (Swagger): `/api/docs/`, схема: `/api/schema/`, ReDoc: `/api/redoc/`
- Әкімші панелі (справочниктер, қызметкерлер): `/admin/`
- Бизнес-ережелер мен рөлдер: [CLAUDE.md](CLAUDE.md)
- Код қайда жазылады, тармақтар, коммиттер, PR: [CONTRIBUTING.md](CONTRIBUTING.md)

## Іске қосу (Docker)

```bash
docker compose up --build
```

→ http://localhost:8000/api/docs/ (Swagger), http://localhost:8000/admin/ — әкімші `admin` / `admin-local`
(тек жергілікті). Миграциялар контейнер іске қосылғанда өздігінен орындалады,
тексеру: `curl http://localhost:8000/api/health/`.

## Docker-сіз

Python 3.13 және PostgreSQL 17 керек.

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pre-commit install                                     # коммит алдында ruff тексереді
cp .env.example .env    # DJANGO_DEBUG=True, DJANGO_SECRET_KEY, DB_* толтырыңыз
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Frontend-пен жұмыс

SPA басқа доменде тұрады және токенмен кіреді:

1. `POST /api/auth/token/` `{"username": "...", "password": "..."}` → `{"token": "..."}`
2. Әр сұранысқа: `Authorization: Token <token>`; ағымдағы пайдаланушы мен бөлімдер — `GET /api/me/`
3. Шығу: `POST /api/auth/logout/` → `204` (токен өшіріледі)

Браузер басқа доменнен сұраныс жібере алуы үшін frontend адресі `CORS_ALLOWED_ORIGINS`-та болуы тиіс
(үтір арқылы; `docker compose`-та әдепкі — `http://localhost:4200`). Frontend dev-сервері `/api`-ді
`localhost:8000`-ге proxy жасаса, CORS керек емес.

## Тесттер

PostgreSQL қажет (тест базасы өздігінен жасалып, өшіріледі):

```bash
python manage.py test
python manage.py makemigrations --check --dry-run    # модельдер мен миграциялар сәйкес пе
```

## Линтер және пішімдеу

[Ruff](https://docs.astral.sh/ruff/) — баптаулары `pyproject.toml`-да (ережелер `E`, `F`, `I`, `B`, `DJ`, жол ұзындығы 120):

```bash
ruff check .            # қателер; --fix — автоматты түзету
ruff format .           # пішімдеу (CI-да: ruff format --check .)
pre-commit run --all-files
```

## Құрылымы

```
config/            баптаулар (settings.py), түбір URL-дар, WSGI/ASGI
kassa/
  common/          домен қателері және оларды HTTP-ға айналдыру, пагинация, іздеу, healthcheck
  inventory/       модельдер, миграциялар, Django админ (кестелер: inventory_*)
  users/           /api/me/, кіру/шығу (токен), рөлдік рұқсаттар
  catalog/         тауарлар, жеткізушілер, қоймалар (оқу)
  documents/       құжатты өткізу және күшін жою — қалдықты өзгертетін жалғыз орын; құжаттар журналы
  pos/             касса: сату, сатудан қайтару
  warehouse/       жеткізушіден қабылдау, жеткізушіге қайтару, есептен шығару
  audits/          түгендеу: бастау, санау, бекіту, күшін жою
  reports/         есептер: қалдық, қозғалыс, айналым, сату, түгендеу
  backups/         manage.py backup_db / restore_db
```

Әр доменде: `services.py` (жазу), `selectors.py` (оқу), `serializers.py`, `apis.py`, `urls.py`, `tests/`.

## Деплой

Qoldanba песочницасында қолданба `Dockerfile` бойынша жиналады, дерекқор мен айнымалыларды платформа
береді (`qoldanba.yaml`), `main`-ге әр merge — жаңа деплой. Талаптар мен CI: [TEMPLATE.md](TEMPLATE.md).
Docker-сіз жеке серверге орнату және резервтік көшірмелер: [DEPLOY.md](DEPLOY.md).
