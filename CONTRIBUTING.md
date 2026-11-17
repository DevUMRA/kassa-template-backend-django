# Командада жұмыс істеу ережелері

Негізгі стайлгайд — [PEP 8](https://peps.python.org/pep-0008/) (Ruff тексереді) және
[HackSoft Django Styleguide](https://github.com/HackSoftware/Django-Styleguide) (ревьюде тексеріледі).
Төменде — осы жобаға қатысты қысқаша мазмұны.

## Код қайда жазылады (HackSoft)

1. **Бизнес-логика — тек `services.py` (жазу) мен `selectors.py` (оқу).** API, сериализатор, модель,
   админ — бизнес-ережені өздері шешпейді, сервисті шақырады.
   Мысал: сату — `kassa/pos/services.py::sale_create`, қалдық есебі — `kassa/reports/selectors.py::stock_report`.
2. **Атау: `<зат>_<әрекет>`**, аргументтер тек атымен (`*`):
   `document_post(*, document, user)`, `receipt_create(*, user, supplier, lines)`, `sale_list(*, user, search=None)`.
3. **API жұқа:** кіріс сериализаторы тексереді → сервис/селектор → шығыс сериализаторы. Бір endpoint —
   бір `APIView` класы (`SaleListCreateApi`, `SaleReturnCreateApi`), ViewSet қолданбаймыз.
   Мысал: `kassa/warehouse/apis.py`.
4. **Модель жұқа:** өрістер, `Meta.constraints`, `clean()`-дағы қарапайым тексеру ғана.
   Модельдер мен миграциялар — `kassa/inventory/models/`, жаңа өріс → `python manage.py makemigrations`.
5. **Қалдықты тек `kassa/documents/services.py` өзгертеді:** `@transaction.atomic`, `select_for_update()`,
   әр өзгеріс `StockMovement`-ке жазылады ([CLAUDE.md](CLAUDE.md), «Strict Rules»).
6. **Қателер:** сервис `BusinessRuleError` (→ 400 `{"detail": [...]}`) немесе `AccessDeniedError` (→ 403)
   лақтырады — `kassa/common/exceptions.py`. API-да `try/except` жазбаймыз, HTTP-ға бір жерде айналады.
7. **Жаңа домен** — `kassa/<домен>/` пакеті: `services.py`, `selectors.py`, `serializers.py`, `apis.py`,
   `urls.py`, `tests/`; жолды `kassa/urls.py`-ға қосыңыз.
8. **API келісімшарты — OpenAPI.** Әр endpoint-те `@extend_schema` болуы тиіс (тест тексереді).
   Жолды, өрісті немесе JSON пішімін өзгерту — frontend-ті бұзады: PR-да анық жазыңыз.
9. **Тесттер міндетті:** сервиске — сервис тесті, endpoint-ке — API тесті (`<домен>/tests/`).

## Линтер

```bash
pip install -r requirements-dev.txt && pre-commit install   # бір рет
ruff check --fix . && ruff format .                         # қолмен
```

CI `ruff check` пен `ruff format --check` таза болмаса, PR merge жасалмайды.

## Тармақтар, коммиттер, PR

- **Тармақ** — Linear тапсырмасының ID-ымен: `feature/QLDB-123-sale-discount`, `fix/QLDB-130-negative-stock`.
  `main`-ге тікелей push жоқ — тек PR арқылы.
- **Коммит** — [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
  `feat(pos): чекке жеңілдік қосу`, `fix(audits): бекітілген түгендеуді қайта санауға тыйым`,
  `test: ...`, `refactor: ...`, `docs: ...`, `chore: ...`.
- **Бір PR = бір тапсырма.** Шағын PR-ды тез қарауға болады; PR үлгісін толтырыңыз
  (Linear тапсырмасы, не өзгерді, қалай тексерілді).
- **Код-ревью** — [Google Engineering Practices](https://google.github.io/eng-practices/review/):
  ревьюер код жобаны жақсарта ма соны қарайды (мінсіз болуын емес); пікір — кодқа, адамға емес;
  ұсыныс пен міндетті түзетуді ажыратыңыз (`Nit:` — міндетті емес). Автор әр пікірге жауап береді.
