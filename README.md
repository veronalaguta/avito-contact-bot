# Avito Contact Bot (ручная выгрузка по кнопке)

MVP под ваш кейс:
- хранит аккаунты Avito (`client_id`, `client_secret`, `sheet_id`),
- запускает выгрузку **вручную** по кнопке в Telegram,
- пишет в Google Sheets только нужный минимум для учета контактов,
- фокус на чатах, звонки включаются опционально.

## Что выгружается
В шаблон таблицы (лист `Лист1`) в колонки `C:G`:
- `дата и время`
- `вид контакта` (`Сообщение` / `Звонок`)
- `источник`
- `ID контакта`
- `статус ответа` (`Чат обработан` / `Звонок обработан`)

Остальные поля (квалификация, воронка, оплата, отзывы) оставляются для ручной работы менеджера.

## 1) Установка
```bash
cd /Users/veronikalagutkina/Documents/Avito/avito_contact_bot
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

## 2) Подготовка Google Sheets API
1. Создайте Service Account в Google Cloud.
2. Включите Google Sheets API.
3. Скачайте JSON-ключ.
4. Дайте доступ этому service account к вашей таблице (как редактор).

Альтернатива без service account:
- оставьте `GOOGLE_SERVICE_ACCOUNT_JSON` пустым,
- выполните локально `gcloud auth application-default login`,
- бот будет использовать ваши пользовательские Google credentials (ADC).

## 3) Переменные окружения
```bash
cp .env.example .env
```
Заполните `.env`:
- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON` (опционально, можно оставить пустым при использовании ADC)
- `BOT_ALLOWED_USER_IDS` (ваш Telegram `user_id`, можно узнать через `/myid`)

## 4) Добавление аккаунта Avito
Можно вставлять и `sheet_id`, и полную ссылку на Google Sheet:
```bash
avito-contact-cli add-account \
  --name "QQROOZA" \
  --client-id "..." \
  --client-secret "..." \
  --sheet "https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit"
```

Проверить список:
```bash
avito-contact-cli list-accounts
```

Ручной запуск синка из CLI:
```bash
avito-contact-cli sync 1
```

## 5) Запуск Telegram-бота
```bash
avito-contact-bot
```

В боте:
- `/start` — кнопки `Выгрузить #ID` по каждому аккаунту.
- `/accounts` — статус аккаунтов.
- `/myid` — ваш Telegram user id.

## Примечания
- Дедупликация событий включена: уже выгруженные записи второй раз не добавляются.
- Если call tracking недоступен по тарифу, просто не используйте `--include-calls`.
- Текущая версия рассчитана на кнопку ручной выгрузки, без фонового hourly-cron.

## Публикация в GitHub
После входа в GitHub:
```bash
cd /Users/veronikalagutkina/Documents/Avito/avito_contact_bot
git init
git add .
git commit -m "Initial MVP: Avito manual export bot"
# затем создайте пустой repo в GitHub и подключите remote
git remote add origin <YOUR_REPO_URL>
git branch -M main
git push -u origin main
```
