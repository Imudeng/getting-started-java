# Фаза 5 — воспроизводимый CI на GitHub-hosted runner (без Selenoid)

## Согласовано (зафиксировано через вопросы)

| Решение | Выбор |
|---|---|
| Триггеры | `push` [master, vodin_homework], `pull_request`, `workflow_dispatch` с inputs: **browser** (chrome/firefox), **headless** (bool, default true), **baseUrl**, **tests** (gradle `--tests` фильтр) |
| Отчёт | **только артефакты** (junit-xml, allure-results со вложениями, allure-report); Pages не трогаем |
| Цель push | **личный форк** `qa-guru/getting-started-java` (общий репозиторий курса не трогаем) |
| `--no-sandbox` | только в CI через `-DnoSandbox=true`, риск задокументирован, локально флаг выключен |
| Allure | **Фаза 4 реализуется в этой задаче** (в коде её нет: коммиты «Фаза 3/4» = только plan-файлы) |

## Версии (зафиксированы, SHA проверены через GitHub API 13.11.2026)

| Инструмент | Версия | SHA |
|---|---|---|
| actions/checkout | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| actions/setup-java | v6.2.0 | `77dd5b2ce225ea11469928ac317850245a74ae78` |
| actions/setup-node | v7.1.0 | `949feb2413d6458794dcd2491c4babbbce0c15c1` |
| actions/upload-artifact | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| browser-actions/setup-chrome | v2.2.0 | `48ad923757ca74d66703209fe939badbdf80f2f4` |
| npm allure (Report 3 CLI) | 3.33.0 | пин в `npx --yes allure@3.33.0` |
| allure-java (адаптеры) | 3.1.1 | allure-jupiter, allure-selenide |
| aspectjweaver | 1.9.27 | поддержка Java 25 подтверждена релизом 04.11.2026 |

**Браузер/драйвер**: на ubuntu-latest (образ 20261104) Chrome 156.0.8078.79 + ChromeDriver 156.0.8078.80 уже есть, но НЕ предполагаем: ставим `setup-chrome@v2.2.0` (парный chrome+chromedriver), затем шаг логирования `google-chrome --version; chromedriver --version`. Selenium 4.49 (из Selenide 7.18.2) приносит Selenium Manager — он повторно сверяет driver↔browser в рантайме; CDP в этой паре поддержан.

## Шаг 0 — предусловия (участие пользователя)

1. **JDK 25 локально отсутствует** (проверено: PATH, JAVA_HOME, ~/.jdks, Program Files) — `gradlew` локально не запускается. Скачать Temurin 25 zip (Adoptium API) в `%USERPROFILE%\.jdks\temurin-25`, `JAVA_HOME` — точечно для команд gradle. Нужен для локальной приёмки Фазы 4.
2. **Форк**: у пользователя форка нет (сверено по публичному списку форков). Варианты: (a) установить gh (`winget install GitHub.cli`) → `gh auth login` (device flow — разовое действие пользователя) → `gh repo fork qa-guru/getting-started-java`; (b) пользователь создаёт форк руками и даёт URL. Добавить remote `fork`.
3. **Actions на форке включены** (на форках по умолчанию выключены — включить в Settings→Actions или баннером на вкладке Actions).

## Шаг 1 — Фаза 4 Allure в коде (по утверждённому `.kilo/plans/allure-report-3.md`)

- `build.gradle`: `allure-jupiter:3.1.1`, `allure-selenide:3.1.1`, `aspectjweaver:1.9.27` (testRuntimeOnly), `junit.jupiter.extensions.autodetection.enabled=true`, `-javaagent:aspectjweaver`, `test { doFirst { delete "allure-results" } }`.
- `TestBase`: `SelenideLogger.addListener("AllureSelenide", new AllureSelenide())` / `removeListener` в `@AfterEach`; **новое**: `if (Boolean.getBoolean("noSandbox")) Configuration.browserCapabilities.addArguments("--no-sandbox", "--disable-dev-shm-usage")` — по умолчанию выключено, локальное поведение не меняется.
- `SearchTests`: `@Step`-хелперы действий; локаторы/assertions/порядок — без изменений.
- `.gitignore`: `allure-results/`, `allure-report/`.
- Локальная мини-приёмка: зелёный прогон; `npx --yes allure@3.33.0 --help`, `generate --help`, `open --help` — точные флаги фиксируются здесь и используются в CI; отчёт открывается, шаги видны.

## Шаг 2 — `.github/workflows/ui-tests.yml`

Аргументы gradle соответствуют properties из build.gradle (`baseUrl`, `browser`, `browserSize`, `headless`):

```yaml
name: UI tests
on:
  push:
    branches: [master, vodin_homework]
  pull_request:
  workflow_dispatch:
    inputs:
      browser:  {description: "chrome | firefox", type: choice, options: [chrome, firefox], default: chrome, required: false}
      headless: {description: "headless", type: boolean, default: true, required: false}
      baseUrl:  {description: "base url", type: string, default: "https://github.com", required: false}
      tests:    {description: "gradle --tests filter", type: string, required: false}

permissions:
  contents: read   # минимальные: только код; без write/Pages/secrets

jobs:
  ui-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
      - uses: actions/setup-java@77dd5b2ce225ea11469928ac317850245a74ae78 # v6.2.0
        with: {distribution: temurin, java-version: "25", cache: gradle}
      - uses: actions/setup-node@949feb2413d6458794dcd2491c4babbbce0c15c1 # v7.1.0
        with: {node-version: "24"}
      - uses: browser-actions/setup-chrome@48ad923757ca74d66703209fe939badbdf80f2f4 # v2.2.0
      - name: Tool versions
        run: java -version; google-chrome --version; chromedriver --version; node -v
      - name: Compile
        run: ./gradlew --no-daemon --console=plain compileTestJava
      - name: UI tests
        run: >
          ./gradlew --no-daemon --console=plain test
          -Dbrowser=${{ inputs.browser || 'chrome' }}
          -Dheadless=${{ inputs.headless != false }}
          -DbaseUrl=${{ inputs.baseUrl || 'https://github.com' }}
          -DnoSandbox=true
          ${{ inputs.tests && format('--tests "{0}"', inputs.tests) || '' }}
      - name: Fail if no test results
        if: always()
        run: |
          total=$(grep -ho 'tests="[0-9]*"' build/test-results/test/*.xml 2>/dev/null | cut -d'"' -f2 | awk '{s+=$1} END {print s+0}')
          echo "JUnit tests total: $total"
          [ "$total" -gt 0 ] || { echo "::error::No test results: build error or 0 tests — not success"; exit 1; }
      - name: Generate Allure report
        if: always()
        run: |
          if [ -n "$(ls -A allure-results 2>/dev/null)" ]; then
            npx --yes allure@3.33.0 generate allure-results -o allure-report
          else
            echo "No allure-results — report skipped (job status decided by test steps)"
          fi
      - name: Upload JUnit XML
        if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with: {name: junit-xml, path: build/test-results/test/, if-no-files-found: warn}
      - name: Upload Allure results
        if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with: {name: allure-results, path: allure-results, if-no-files-found: warn}
      - name: Upload Allure report
        if: always()
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9 # v7.0.2
        with: {name: allure-report, path: allure-report, if-no-files-found: warn}
```

Флаги `generate` (`-o` vs `--output`) фиксируются фактическим `--help` на шаге 1.

Заложенное поведение:
- **ошибка компиляции ≠ падение тестов**: отдельный шаг `Compile`; при его падении `test` не запускается → junit/allure отсутствуют → шаг «Fail if no test results» даёт явное сообщение, `allure-report` не создан (warn в аплоаде), job failure.
- **падение тестов**: шаг `UI tests` падает — job остаётся failure (аплоады `if: always()` статус не маскируют); сохраняются junit-xml, allure-results со вложениями AllureSelenide (screenshot + page source), готовый allure-report.
- **0 тестов — не успех**: guard `total > 0`.
- dispatch-дефолты: на push/PR `inputs.*` пусты → `chrome`, headless: `${{ inputs.headless != false }}` → "true".

Безопасность: все actions закреплены SHA; `permissions: contents: read`; секретов нет; `pull_request` (НЕ `pull_request_target`) — код из fork PR работает без секретов и с read-only токеном; `--no-sandbox` только в CI (компромисс: ослабление изоляции Chrome на ephemeral-раннере GitHub, риск принят и описан в комментарии workflow).

## Шаг 3 — проверка на форке (приёмка)

0. (Разово) форк + Actions on + `git remote add fork <url>`; push `vodin_homework`.
1. **Success**: push-триггер; анонимный API `GET /repos/<fork>/actions/runs?branch=vodin_homework` → conclusion `success`; артефакты `junit-xml`, `allure-results` (внутри `*-attachment.png/.html` — проверить скачиванием), `allure-report`.
2. **Контролируемое падение**: временная ветка `ci/check-fail` — ожидаемый текст теста 1 → `NO-SUCH-REPO`. Ожидание: job `failure`; три артефакта на месте; в отчёте причина + failed step + вложения.
3. **Ошибка сборки**: временная ветка `ci/check-compile-error` — битый синтаксис. Ожидание: job `failure` именно на шаге `Compile`; junit-xml/allure-report отсутствуют; по упавшему шагу статус отличается от п.2.
4. **workflow_dispatch + overrides**: срабатывает только когда workflow есть в дефолтной ветке форка (ловушка: dispatch-файлы берутся из дефолтной ветки; факт регистрации проверить `GET /actions/workflows`). Проверка override: `tests=SearchTests.successfulSearchTest` → в junit-xml ровно 1 тест, job success. Для этого шага — merge `vodin_homework` в `master` форка (с ведома пользователя).
5. **Уборка**: удалить временные ветки `ci/check-fail`, `ci/check-compile-error` (на форке и локально).

## Риски / оговорки

- gh CLI и токена GitHub локально нет: шаг 0 требует device-flow авторизацию gh (разовое действие пользователя) либо ручное создание форка с передачей URL.
- На форках Actions по умолчанию выключены — без включения пуши не запустят CI.
- Chrome на hosted runner без `--no-sandbox` падает — компромисс принят (только CI, документирован).
- Firefox из dispatch-input: geckodriver подтянет Selenium Manager; эталонная конфигурация — chrome.
- Пушей в общий `origin` (qa-guru/getting-started-java) не будет.