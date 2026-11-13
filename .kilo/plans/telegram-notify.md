# Фаза 6 — уведомление о результатах прогона (Telegram) поверх CI

## Согласовано (зафиксировано через вопросы)

| Пункт | Решение |
|---|---|
| Объём | **end-to-end**: сначала реализуются утверждённые Фазы 4 (`.kilo/plans/allure-report-3.md`) и 5 (`.kilo/plans/ci-github-hosted.md`), затем уведомление. Внешние действия (push в форк, реальная отправка) — каждое с явного согласия |
| Уведомляющий CI | workflow `ui-tests.yml`, GitHub-hosted `ubuntu-latest`, финальный шаг job'а `ui-tests` |
| Исходы | success ✅ · тесты упали ❌ · ошибка сборки/тесты не запускались 🛑 · «0 тестов» ⚠️ (отдельно от 🛑) · **cancelled — не слать** (лог skip) |
| Secrets | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`; отсутствует → «notify skipped: secrets not configured», exit 0, статус job не меняется |
| Ошибка API | санитизированный лог (без токена/chat_id даже в текстах исключений), exit 0, job-статус не трогаем; доп. страховка — `continue-on-error: true` на шаге |
| Реальная отправка | только после локальной fixtures/mock-приёмки и добавления secrets пользователем; затем сверка фактического сообщения |

## Анти-утечка (обязательно)

- Токен/chat_id только из `secrets.*` → `env` шага; в коде дефолтов нет.
- Никаких `set -x`, `curl -v`/`-x` (HTTP делает `urllib`, команда одна: `python3 scripts/ci_notify.py`).
- Любая строка ошибки прогоняется через `sanitize()`: подстроки токена и chat_id → `***`.
- Тест сценария API-ошибки ассертит: ни в stdout, ни в stderr нет значения токена.

## Реализация

### `scripts/ci_notify.py` (Python 3.10+, только stdlib)

Вход через env (все не-секреты задаёт workflow):
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (секреты), `RESULT_DIR` (по умолчанию `build/test-results/test`), `PROJECT`, `WORKFLOW_NAME`, `RUN_BRANCH`, `RUN_SHA`, `RUN_EVENT`, `RUN_URL`, `JOB_STATUS` (`${{ job.status }}`), `TELEGRAM_API_BASE` (дефолт `https://api.telegram.org` — **только** хук для mock-приёмки, секретов не содержит), `TELEGRAM_TIMEOUT` (дефолт 10 с).

Статистика — **только из JUnit XML** (Gradle/surefire формат: `<testsuite tests failures errors skipped>`), никаких файлов Allure-отчёта:
- glob `RESULT_DIR/TEST-*.xml` (несколько файлов → суммируем);
- парсим корень `<testsuite>` или обёртку `<testsuites>`; считаем атрибуты узла `<testsuite>` и **не спускаемся внутрь него** — вложенные `<testsuite>` не удваиваются (regression-фикстура);
- `failed=Σfailures`, `errors=Σerrors`, `skipped=Σskipped`, `passed=Σtests − failures − errors − skipped`;
- битый XML → не тихая ошибка: итоговый статус «результаты повреждены» (+ перечисление файлов), exit 0.

Маппинг статуса (различаем «не запускались» и «0 тестов»):
| условие | текст статуса |
|---|---|
| `JOB_STATUS == cancelled` | (не отправляем, exit 0) |
| XML-файлов нет | 🛑 Сборка/подготовка упали — тесты не запускались |
| файлы есть, Σtests == 0 | ⚠️ Тесты не прошли: 0 тестов |
| failures+errors > 0 | ❌ Тесты упали (failed/errors) |
| JOB_STATUS failure, но failures+errors == 0 | ❌ Сбой job'а после тестов |
| JOB_STATUS success | ✅ Все тесты зелёные |

Формат сообщения (plain text, без parse_mode — экранирование не нужно):
```
{PROJECT} — {WORKFLOW_NAME} (GitHub Actions)
{RUN_BRANCH} @ {RUN_SHA:0:7} (push|pull_request|workflow_dispatch)
Статус: {статус}
passed {p} · failed {f} · errors {e} · skipped {s} · total {t}
Run: {RUN_URL}
```
(при 🛑/битых XML строка статистики заменяется пояснением)

Отправка: `urllib.request.Request(POST {TELEGRAM_API_BASE}/bot{token}/sendMessage, json={chat_id, text}, timeout=TELEGRAM_TIMEOUT)`. Успех = HTTP 200 **и** `{"ok": true}` в теле. Любой другой исход (не-200, ok=false, HTTPError/URLError, timeout, битый ответ) → `notify: telegram API error: <код/тип>` после `sanitize()`. **Все пути → exit 0** (уведомление никогда не меняет статус прогона).

### `scripts/test_ci_notify.py` + `scripts/fixtures/junit/` (stdlib-приёмка без сети)

Mock HTTP: `http.server` на 127.0.0.1, эфемерный порт, `TELEGRAM_API_BASE=http://127.0.0.1:<порт>`; handler по сценарию возвращает: `200 {"ok":true,"result":{}}` (с захватом payload), `200 {"ok":false,"description":"chat not found"}`, `401`, `500`, подвес (sleep > timeout), подсчёт запросов. В качестве токена — маркер `FAKE-TOKEN-123`, который ассертится отсутствующим в логах.

Фикстуры: `success.xml`, `failure.xml` (failures=1), `error.xml` (errors=2), `skipped.xml`, `multi-1.xml`+`multi-2.xml` (суммирование), `nested.xml` (`<testsuites>`-обёртка — не двойной счёт), `nested_inner.xml` (testsuite-в-testsuite — регресс на удвоение), `broken.xml`, пустой каталог, отсутствующий каталог.

Сценарии (subprocess ci_notify.py с контролируемым env; каждый проверяет exit code и захваченный payload/логи):
1. success → ✅, counts 3/0/0/0, RUN_URL в тексте
2. failure → ❌ failed 1
3. errors считаются отдельно от failures
4. skipped в сообщении
5. multi-файлы: сумма
6. nested/nested_inner: total == число реальных leaf-тестов (без удвоения)
7. broken.xml → «повреждены», exit 0
8. нет XML + JOB_STATUS=failure → 🛑 «не запускались» (и НЕ «0 тестов»)
9. XML с 0 тестов → ⚠️ «0 тестов»
10. секреты пусты → skipped, **0 запросов к моку**
11. HTTP 500 → sanitized-ошибка, exit 0
12. 200 но ok=false → «ok=false», exit 0
13. timeout (sleep 2s, timeout 0.5s) → «timeout», exit 0
14. во всех error-сценариях stdout/stderr не содержат `FAKE-TOKEN-123`/chat_id
15. exit code == 0 во всех 15 (failure job'а не маскируется и не усиливается)

Запуск локально: `python scripts/test_ci_notify.py` — нужен Python (`winget install --id Python.Python.3.12 -e`, разово).

### Шаг в `.github/workflows/ui-tests.yml` (последним, после uploads)

```yaml
      - name: Notify Telegram
        if: always()
        continue-on-error: true
        env:
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: ${{ secrets.TELEGRAM_CHAT_ID }}
          JOB_STATUS: ${{ job.status }}
          PROJECT: ${{ github.repository }}
          WORKFLOW_NAME: ${{ github.workflow }}
          RUN_BRANCH: ${{ github.ref_name }}
          RUN_SHA: ${{ github.sha }}
          RUN_EVENT: ${{ github.event_name }}
          RUN_URL: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}
        run: python3 scripts/ci_notify.py
```

python3 на ubuntu-latest предустановлен. `permissions` не меняются (секреты — не permissions).

## Порядок выполнения

1. Локальная среда: Temurin JDK 25 zip → `~\.jdks` (по Фазе 5), Python 3.12 (winget).
2. **Фаза 4** (Allure) по утверждённому плану + локальная мини-приёмка (зелёный прогон, отчёт со шагами/вложениями, флаги allure@3.33.0 по `--help`).
3. **Фаза 5**: `ui-tests.yml` + форк + Actions + пуш `vodin_homework` → зелёный прогон с артефактами (приёмка Фазы 5). **Без** notify-шага.
4. `ci_notify.py` + harness → локально 15/15 зелёных.
5. Notify-шаг в workflow → пуш **без secrets** в форк: лог «notify skipped», статус run = статус тестов. Ветка `ci/notify-fail` (падение теста) → run остаётся **failure** с корректным локом уведом-шага — демонстрация «уведомление не маскирует failure»; ветку удалить.
6. Пользователь заводит бота и кладёт `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` в secrets форка (токен мне не передаётся) → с явного согласия → реальные прогоны: success (и опционально одна временная failed-ветка) → сверяю фактическое сообщение: проект, CI, branch/sha, статус, passed/failed/skipped/total против junit-XML того же run'а, кликабельная ссылка. Временные ветки — удалить.

## Риски

- Реальная отправка невозможна до действий пользователя (бот + secrets); без них приёмка останавливается на шаге 5, это валидное состояние.
- Формат JUnit XML: Gradle пишет `<testsuite>` per class; регресс на двойной счёт и «error vs failure» покрыт фикстурами.
- Telegram rate-limit/ошибки сети — только санитизированный лог; повторных попыток нет (намеренно, чтобы не растягивать job).
- Секретов в `build.gradle`/репозитории не появляется; в артефактах уведомлений нет.