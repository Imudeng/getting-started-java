# Jenkins: те же тесты и Allure-отчёт на jenkins.qa.guru

> **Статус (16.11):** Jenkinsfile внесён в корень репозитория (этим же коммитом — патч `CI_NAME` в `ci_notify.py` + 18-й сценарий harness). Job на jenkins.qa.guru **не создан**, матрица проверок (SUCCESS/UNSTABLE/FAILURE/notify) **не исполнена** — интеграция помечена непроверенной.
> **Ограничения:** создание job требует прав админа курса (делает пользователь по инструкции ниже); наличие Chrome на `java-jdk21` агенте не доказано (план Б — одноразовый `docker{}` по пробе стадии Versions); JDK 25 подтянется foojay (агент отдаёт 21).

## Согласовано (зафиксировано через вопросы)

| Пункт | Решение |
|---|---|
| Jenkins | внешний `https://jenkins.qa.guru` (курс). Job создаёт **пользователь вручную** по моей инструкции (Item.Configure только у admin); я сверяю прогоны через публичный API/логи |
| Агент | label `java` (`java-jdk21-jenkins-agent-*`, docker-пул). JDK 25 подтянет gradle toolchain (foojay в settings.gradle уже есть). Chrome **не предполагаем**: первый прогон логирует версии — план Б: одноразовый `docker {}` контейнер с Chrome на том же агенте |
| Статусы | тесты → **UNSTABLE** (жёлтый, идиома Jenkins, junit step проставляет сам); ошибка компиляции / отсутствие результатов / «0 тестов» → **FAILURE**; ABORTED → notify «cancelled» не шлёт (скрипт умеет) |
| Отчёт | закреплённый CLI `npx --yes allure@3.33.0 generate` — та же команда, что локально и в GHA; плагины не ставим (в контроллере есть `allure-jenkins-plugin@3.0.0` — доказан на демо-job'ах курса, но по согласованию берём CLI; плагин — опция на будущее) |
| SCM | пуш `vodin_homework` в `origin` = публичный `qa-guru/getting-started-java`; Jenkins-from-SCM **без credentials** (публичный репо) |
| Параметры | `BROWSER` (chrome/firefox), `HEADLESS` (bool, true), `BASE_URL`, `TESTS` (фильтр), `NO_SANDBOX` (bool, **default OFF** — это компромисс root/docker-окружений, не копия GHA-настройки) |
| Credentials | Secret text `telegram-bot-token`, `telegram-chat-id`; при отсутствии — `withCredentials` кидает → ловим → «notify skipped», статус не меняем |

## Шаг 1 — правка `scripts/ci_notify.py` (CI-агностичность)

Единственная строка, зашитая под GHA, — заголовок сообщения. Правим:

```python
# build_message():
f"{env.get('PROJECT', '?')} — {env.get('WORKFLOW_NAME', 'CI')} ({env.get('CI_NAME', 'GitHub Actions')})",
```

Harness: +сценарий 18 — `CI_NAME=Jenkins` в тексте «(Jenkins)»; остальные 17 не трогаем, гоняем все.

## Шаг 2 — `Jenkinsfile` (корень репозитория)

```groovy
// Те же команды wrapper/отчёта, что локально и в GitHub Actions.
// Статусы: упавшие тесты → UNSTABLE; ошибка компиляции / нет результатов / 0 тестов → FAILURE.
pipeline {
    agent { label 'java' }

    parameters {
        choice(name: 'BROWSER', choices: ['chrome', 'firefox'], description: 'browser for Selenide')
        booleanParam(name: 'HEADLESS', defaultValue: true, description: 'headless')
        string(name: 'BASE_URL', defaultValue: 'https://github.com', description: 'Selenide baseUrl')
        string(name: 'TESTS', defaultValue: '', description: 'gradle --tests filter (empty = all)')
        booleanParam(name: 'NO_SANDBOX', defaultValue: false,
            description: 'Chrome --no-sandbox ONLY for root/docker agents; deliberately OFF by default (not a copy of the GHA setting)')
    }

    options { timestamps(); disableConcurrentBuilds(); buildDiscarder(logRotator(numToKeepStr: '20')) }

    environment { CI_NAME = 'Jenkins' }

    stages {
        stage('Versions') {
            steps {
                sh '''#!/bin/bash
                  java -version 2>&1 | head -1
                  node -v; npm -v
                  (python3 --version || echo "PYTHON3: NOT FOUND")
                  (google-chrome --version || chromium --version || chromium-browser --version || echo "CHROME: NOT FOUND")
                  (chromedriver --version || echo "CHROMEDRIVER: NOT FOUND")'''
            }
        }
        stage('Compile') {
            steps { sh './gradlew --no-daemon --console=plain compileTestJava' }
        }
        stage('UI tests') {
            steps {
                script {
                    def filter  = params.TESTS?.trim() ? "--tests '${params.TESTS.trim()}'" : ''
                    def sandbox = params.NO_SANDBOX ? '-DnoSandbox=true' : ''
                    env.TEST_RC = sh(returnStatus: true, script: """
                        ./gradlew --no-daemon --console=plain test \
                          -Dbrowser=${params.BROWSER} -Dheadless=${params.HEADLESS} \
                          -DbaseUrl=${params.BASE_URL} ${sandbox} ${filter}""")
                }
            }
        }
        stage('Require test results') {
            steps {
                sh '''#!/bin/bash
                  total=$(grep -ho 'tests="[0-9]*"' build/test-results/test/*.xml 2>/dev/null | cut -d'"' -f2 | awk '{s+=$1} END {print s+0}')
                  echo "JUnit tests total: $total"
                  [ "$total" -gt 0 ] || { echo "No test results: build error or 0 tests — not success"; exit 1; }'''
            }
        }
        stage('Generate Allure report') {
            steps {
                sh '''#!/bin/bash
                  if [ -n "$(ls -A allure-results 2>/dev/null)" ]; then
                    npx --yes allure@3.33.0 generate allure-results -o allure-report
                  else
                    echo "No allure-results — report skipped (status decided by earlier stages)"
                  fi'''
            }
        }
    }

    post {
        always {
            script {
                if (env.TEST_RC != '0' && currentBuild.currentResult == 'SUCCESS') {
                    currentBuild.result = 'UNSTABLE'   // тесты вернули не-0, но junit ещё не пометил
                }
            }
            junit testResults: 'build/test-results/test/*.xml', allowEmptyResults: true, keepLongStdio: true
            archiveArtifacts artifacts: 'allure-results/**', allowEmptyArchive: true, defaultExcludes: false
            archiveArtifacts artifacts: 'allure-report/**', allowEmptyArchive: true
            script {
                def status = currentBuild.currentResult == 'SUCCESS' ? 'success'
                           : currentBuild.currentResult == 'ABORTED' ? 'cancelled' : 'failure'
                try {
                    withCredentials([string(credentialsId: 'telegram-bot-token', variable: 'TELEGRAM_BOT_TOKEN'),
                                     string(credentialsId: 'telegram-chat-id', variable: 'TELEGRAM_CHAT_ID')]) {
                        sh """#!/bin/bash
                          JOB_STATUS='${status}' PROJECT='${env.JOB_NAME}' WORKFLOW_NAME='Jenkins pipeline' \
                          RUN_BRANCH='${env.GIT_BRANCH ?: 'vodin_homework'}' RUN_SHA='${env.GIT_COMMIT ?: ''}' \
                          RUN_EVENT='jenkins' RUN_URL='${env.BUILD_URL}' CI_NAME='Jenkins' \
                          TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID python3 scripts/ci_notify.py"""
                    }
                } catch (e) {
                    // нет credentials или сеть/Telegram легли — статус прогона НЕ трогаем
                    echo "notify skipped/failed: ${e.message?.take(150)}"
                }
            }
        }
    }
}
```

Заложенное:
- `sh(returnStatus)` в тестовой стадии: упавшие тесты не валят пайплайн раньше времени → junit сам окрасит **UNSTABLE**; `TEST_RC!=0` без junit-фида → UNSTABLE вручную; компиляция/гард — падают как обычно → **FAILURE**.
- `allowEmptyResults/allowEmptyArchive` — диагностика сохраняется при любом исходе, при ошибке компиляции не создаёт вторичный шум (гард уже упал).
- Секреты: только `withCredentials`; в командной строке — лишь **имена** переменных (`TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID cmd` — проброс env, не значения); вывод ошибок уведомлений — только текст исключения Jenkins (id credentials, без значений).
- `--no-sandbox` — параметр с default OFF.

### План Б для браузера (только если Versions покажет CHROME: NOT FOUND)

Заменяем `agent { label 'java' }` на run-once docker-контейнер на том же агенте (агенты помечены `docker`), без удалённой инфраструктуры и следов на хосте. Образ подбирается **пробным прогоном** (`docker.image(...).inside { chrome --version }`), кандидаты: `cimg/openjdk:25.0-node` (проверка наличия chrome) либо базовый + установка в контейнер; точный образ фиксируем по факту пробы — не «на веру».

## Шаг 3 — пуш и job (действия пользователя по инструкции)

1. Я пушу `vodin_homework` в `origin qa-guru/getting-started-java` (ваша авторизация GCM через браузер — интерактивный шаг) — [x] согласовано.
2. Вы создаёте job: **New Item → Pipeline** `vodin_homework-ui-tests` → Pipeline: *Pipeline script from SCM* → Git → `https://github.com/qa-guru/getting-started-java.git`, Branch `*/vodin_homework`, Script Path `Jenkinsfile`, Credentials: none → Save → **Build Now** (параметры объявятся после первого прогона).
3. Реальная отправка — опционально потом: два Secret text `telegram-bot-token`/`telegram-chat-id`.

## Шаг 4 — проверка на реальном агенте (приёмка)

| # | Сценарий | Ожидание |
|---|---|---|
| 1 | Plain build | SUCCESS; junit-тренд; архивы allure-results+report; Versions: версии java/node/chrome |
| 2 | ветка `ci/jenkins-check-fail` (временная, текст assertion → `NO-SUCH-REPO`) | **UNSTABLE**; junit показывает failure; в allure-results `.png`+`.html`; notify-лог «sent/skipped» с текстом failure |
| 3 | ветка `ci/jenkins-compile-error` (битый синтаксис) | **FAILURE** на Compile; allure-report НЕ заархивирован; статус ≠ UNSTABLE |
| 4 | параметр `TESTS=SearchTests.nope` (нет таких тестов → gradle падает без XML) | **FAILURE** на «Require test results» (отличие от п.2: красный, а не жёлтый) |
| 5 | credentials не заведены | в console log «notify skipped», цвет билда не тронут |
| 6 | (после ваших secrets) repeat п.1/п.2 | сообщение в Telegram: `(Jenkins)`, branch/sha, статус, passed/failed/skipped, BUILD_URL |

Временные ветки `ci/jenkins-*` удалить после проверки (и локально, и на origin).

Локально до пуша: полный harness `test_ci_notify.py` (18 сценариев), gradle-тесты зелёные. Jenkinsfile синтаксически проверяется первым же прогоном (declarative; без плагинов кроме штатных git/junit/artifacts/credentials).

## Риски

- foojay-загрузка JDK 25 на холодном агенте ~+1–2 мин (toolchain 25 зафиксирован; агент отдаёт JDK 21).
- Если у java-агентов нет node/npm (демо-джобы курса используют npx — косвенно есть, но проверим в Versions): уведомление/отчёт падают изолированно (post/catch), статус тестов не маскируется; резерв отчёта — плагин `allure-jenkins-plugin@3.0.0`, уже установлен в контроллере (решение — только по факту пробы).
- Публичный origin курса: в истории коммитов метаданные автора (vodin@gnivc.ru) — как и в существующих ваших коммитах там.