# Job Compass

Локальное приложение для поиска вакансий по списку карьерных сайтов. Пользователь вводит адреса сайтов, примерную должность и необязательные ключевые слова, а приложение возвращает подходящие вакансии со ссылками.

## Как работает поиск

- `auto` — использует AI Job Search через локальный `codex exec`, если задан `AI_JOB_SEARCH_ROOT`; иначе запускает встроенный crawler карьерных сайтов.
- `ai_job_search` — требует локальную копию [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) и авторизованный Codex CLI.
- `html` — совместимое имя встроенного crawler: он вызывает известные публичные API, использует поиск самого сайта, разбирает карточки вакансий и `JobPosting` JSON-LD. В отчёт попадают только прямые ссылки на отдельные вакансии.

AI Job Search не является HTTP API. В этом проекте backend безопасно запускает его `scrape`-workflow через локальный `codex exec`, получает структурированный JSON и показывает его во frontend. Для личного использования отдельный OpenAI API-ключ не нужен, если Codex CLI уже авторизован вашей подпиской.

Career Ops подключается отдельно как локальный движок анализа резюме и вакансий. Backend
проверяет полный checkout Career Ops, наличие Codex CLI и состояние onboarding через его
`doctor.mjs`. Пользовательские резюме и созданные документы хранятся в отдельной директории,
а не в репозитории Job Compass.

## Быстрый запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

Откройте `http://localhost:3000`.

## Хранение настроек в Supabase

Job Compass может хранить карьерные сайты, должности, ключевые слова и исключения в
PostgreSQL Supabase. Схема нормализована до 3НФ и находится в
`supabase/migrations/001_search_settings.sql`.

1. Создайте проект Supabase.
2. Откройте **SQL Editor**, вставьте содержимое файла миграции и выполните запрос.
3. В **Connect → Session pooler** скопируйте PostgreSQL connection string.
4. Создайте локальный `.env` из `.env.example` и добавьте строку подключения:

```env
SUPABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@HOST:5432/postgres?sslmode=require
```

Это именно серверная строка PostgreSQL Session Pooler, а не публичный HTTPS URL проекта.
Если пароль содержит специальные символы, закодируйте их для URL. `.env` не добавляется
в Git. После изменения конфигурации перезапустите приложение:

```bash
docker compose up -d --build
```

При первом подключении пустой Supabase автоматически получает уже сохранённые локальные
настройки. Если Supabase не настроен или временно недоступен, приложение продолжает
работать через локальное хранилище браузера.

Чтобы включить AI Job Search, клонируйте репозиторий отдельно, установите portal CLI по его инструкции и укажите абсолютный путь в `.env`:

```bash
git clone https://github.com/ai-job-search-dev/ai-job-search.git
cd ai-job-search
python3 tools/install_portal_clis.py
```

```env
SEARCH_PROVIDER=auto
AI_JOB_SEARCH_ROOT=/absolute/path/to/ai-job-search
```

Если переменная пуста, используется встроенный crawler. Docker по умолчанию также работает в этом режиме: конфигурация и авторизация локального Codex намеренно не копируются внутрь контейнера. Для AI Job Search запустите backend локально по инструкции ниже.

## Локальный Career Ops

Установите полный Career Ops рядом с Job Compass:

```bash
cd /path/to/parent
npx @santifer/career-ops init
```

Затем укажите checkout и отдельную директорию пользовательских данных:

```env
CAREER_OPS_PROJECT_ROOT=/absolute/path/to/career-ops
CAREER_OPS_DATA_DIR=/absolute/path/to/job-compass-data/career-ops
CAREER_OPS_QUICK_MODEL=gpt-6-luna
# Optional: quick checks use Groq instead of Codex when this key is set.
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
```

`GET /api/health` показывает, установлен ли движок, доступен ли Codex и какие файлы onboarding
ещё отсутствуют. Пока onboarding не завершён, поиск вакансий продолжает работать как раньше,
а Career Ops не запускает анализ или генерацию документов.

В разделе «Резюме» можно загрузить PDF, DOCX, TXT или MD размером до 10 МБ. Backend локально
сохраняет исходник и извлечённый текст в `CAREER_OPS_DATA_DIR`; эта директория исключена из Git.

Проверка совместимости работает в двух режимах. Быстрая проверка использует уже извлечённый
текст вакансии, компактный prompt и постоянный кеш по версии вакансии и резюме. Полный отчёт
Career Ops A–G запускается отдельно из окна результата. Если задан `GROQ_API_KEY`, быстрые
проверки выполняются через Groq; иначе используется `CAREER_OPS_QUICK_MODEL` через Codex CLI.
Извлечённый текст показывается для проверки, но на этом этапе ещё не становится подтверждённым
`cv.md` Career Ops и не передаётся модели.

## Локальная разработка

Backend:

```bash
python3 -m venv .venv
.venv/bin/pip install -e './backend[dev]'
.venv/bin/uvicorn app.main:app --reload --app-dir backend
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Frontend будет доступен на `http://localhost:5173`, API — на `http://localhost:8000`.

## Проверки

```bash
.venv/bin/ruff check backend
.venv/bin/pytest backend
cd frontend && npm test && npm run build
docker compose build
```

CI запускает backend/frontend тесты и Docker-сборку. После успешной проверки ветки автоматически создаётся pull request в `main`. В настройках GitHub репозитория нужно разрешить Actions создавать pull request: **Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**.

## Ограничения

- CAPTCHA, авторизация и Cloudflare могут заблокировать автоматический поиск.
- Crawler использует API-адаптеры для МТС и Яндекса с пагинацией, а для остальных сайтов пробует форму поиска, распространённые query-параметры, обычные карточки и `JobPosting` JSON-LD. Для сайта с уникальным закрытым API может понадобиться небольшой адаптер в `backend/app/services/site_adapters.py`.
- AI Job Search лучше работает с установленными portal skills; для нового постоянного источника его `/add-portal` создаёт отдельный адаптер.
- Backend блокирует локальные и приватные адреса, ограничивает число сайтов, размер ответа и время выполнения для защиты от SSRF и зависаний.
- Приложение только собирает ссылки и не отправляет отклики автоматически.

