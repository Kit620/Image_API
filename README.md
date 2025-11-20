# Image_API

Асинхронный сервис для загрузки изображений, их конвертации в JPEG, опциональной компрессии и выдачи по ID. Реализован на `aiohttp`, хранит данные в PostgreSQL и использует `asyncpg`.

## Требования

- Python 3.11+
- PostgreSQL 14.1+ **или** Docker + Docker Compose

## Быстрый старт

### Вариант A. Docker (рекомендуется)

```bash
# 1. Поднимаем контейнер с PostgreSQL
docker-compose up -d

# 2. Устанавливаем зависимости
pip install -r requirements.txt

# 3. Запускаем API (таблица создастся автоматически!)
python -m app.main
```

**Важно:** Схема БД создаётся **автоматически** при первом запуске сервера! Файл `init_db.sql` опционален.

### Вариант B. Локальный PostgreSQL

```bash
# 1. Создаём базу и пользователя
createdb image_db
psql -d image_db -c "CREATE ROLE \"user\" WITH LOGIN PASSWORD 'password';"
psql -d image_db -c "GRANT ALL PRIVILEGES ON DATABASE image_db TO \"user\";"

# 2. Устанавливаем зависимости
pip install -r requirements.txt

# 3. При необходимости меняем DATABASE_URL в .env
# DATABASE_URL=postgresql://user:password@localhost:5432/image_db

# 4. Запускаем API (таблица создастся автоматически!)
python -m app.main
```

### (Опционально) Создание схемы вручную

Если хотите создать таблицу вручную до запуска сервера:

```bash
psql postgresql://user:password@localhost:5432/image_db -f init_db.sql
```

Это не обязательно, т.к. сервер создаст таблицу сам при первом запуске через метод `init_schema()` в `app/db.py`.

## Использование API

### Эндпоинты

- **POST /images** - Загрузка и обработка изображения
- **GET /images/{id}** - Получение изображения по ID
- **GET /logs** - Просмотр логов сервера

## Структура проекта

```
.
├── app/
│   ├── __init__.py
│   ├── config.py      # Конфигурация из .env
│   ├── db.py          # Работа с PostgreSQL (включая init_schema)
│   ├── main.py        # Основной файл с API эндпоинтами
│   ├── schemas.py     # Marshmallow схемы для Swagger
│   └── utils.py       # Обработка изображений (Pillow)
├── docker-compose.yml # PostgreSQL контейнер
├── init_db.sql        # SQL схема (опционально, для ручного создания)
├── pyproject.toml     # Настройки линтеров (mypy, black, isort)
├── README.md
├── requirements.txt   # Python зависимости
└── .env              # Переменные окружения (секреты)
```

## Как работает создание схемы БД

При запуске сервера (`python -m app.main`) происходит:

1. **Вызывается** `on_startup()` → `db.connect()`
2. **Создаётся** пул соединений к PostgreSQL
3. **Автоматически выполняется** `db.init_schema()`
4. **Создаются таблицы** через `CREATE TABLE IF NOT EXISTS`

Это означает:
- ✅ Таблица создаётся **автоматически** при первом запуске
- ✅ При повторном запуске ничего не происходит (`IF NOT EXISTS`)
- ✅ Файл `init_db.sql` нужен для **ручного создания** (опционально)


## Swagger UI

API документация доступна по адресу: **http://localhost:8080/api/docs**

Для тестирования эндпоинтов:
1. Нажмите **"Authorize"** (справа вверху)
2. Введите: `Bearer xK6mP2vQ7wR4tY8uI0oP3aS6dF9gH2jK4`
3. Нажмите **"Authorize"** → **"Close"**
4. Тестируйте эндпоинты через интерфейс!

