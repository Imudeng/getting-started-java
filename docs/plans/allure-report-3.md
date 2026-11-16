# Allure Report 3: понятный отчёт с диагностикой падений

> **Статус (16.11):** реализовано (`d14a601`) и проверено локально — зелёный прогон с именованными `@Step`, контролируемое падение со screenshot+page source, флаги allure@3.33.0 взяты из фактического `--help`; отчёт в CI-артефакте подтверждён прогоном Actions #2 (упавшего).
> **Ограничения:** см. «Риски» ниже; зелёного CI-прогона с отчётом нет (Linux-раннер — план ci-github-hosted).

## Согласовано (зафиксировано через вопрос)

| Слой | Инструмент | Версия | Обоснование |
|---|---|---|---|
| JVM-адаптер (пишет results) | `io.qameta.allure:allure-jupiter` (+транзитивно `allure-junit-platform`) | **3.1.1** | POM собран против junit-platform-launcher **6.1.0** — единственный слой, совместимый с нашим JUnit **6.1.3**; `allure-jupiter` регистрирует Extension через `META-INF/services`, `allure-junit-platform` — TestExecutionListener через SPI; `META-INF/aop-ajc.xml` уже в нём |
| JVM-адаптер (вложения/шаги Selenide) | `io.qameta.allure:allure-selenide` | **3.1.1** | класс `AllureSelenide implements com.codeborne.selenide.logevents.LogEventListener` — API есть в selenide-core 7.18.2 (проверено в jar) |
| Аспект-движок | `org.aspectj:aspectjweaver` | **1.9.27** | реликт 04.11.2026, поддерживает Java 25–27 (release notes V1_9_25/V1_9_27) |
| CLI-генератор (собирает HTML) | npm `allure` (Allure **Report 3**) | **3.33.0**, запуск `npx --yes allure@3.33.0` | engines node>=22.18, у нас 24.13.1 ✓; Report 2 CLI — замороженная линейка, её адаптер `allure-junit5` остановлен на 2.35.6 и официально не поддерживает JUnit 6. **Не смешивать 2.x-адаптер с 3.x-генератором** |
| Шаги | `@Step` + `-javaagent:aspectjweaver` | — | выбор пользователя; приёмка обязывает видеть шаги в отчёте |

Ловушки учтены: `allure-junit5` не берём (2.35.6 = тупик); @Step без агента молча не работает — агент добавляется в `test { jvmArgs }` и проверяется фактическими шагами в отчёте; флаги CLI зафиксируем по реальному `--help` версии 3.33.0 перед генерацией (по README v3: `generate <resultsDir>`, `open <reportDir>`, `--results-dir`).

## Шаг 0 — запуск JDK (блокатор среды)

`java`/`JAVA_HOME` отсутствуют (проверено: PATH, JAVA_HOME User/Machine, ~/.jdks, Program Files, ~/.gradle/jdks), а Gradle не стартует без JVM:
`ERROR: JAVA_HOME is not set...`.

- Скачать Temurin JDK 25 zip с Adoptium API (`https://api.adoptium.net/v3/binary/latest/25/ga/windows/x64/jdk/hotspot/normal/eclipse`) в `%USERPROFILE%\.jdks\temurin-25\` (без админ-прав).
- Все команды gradle: `$env:JAVA_HOME="$env:USERPROFILE\.jdks\temurin-25"; .\gradlew.bat ...`.
- Фолбэк: `winget install EclipseAdoptium.Temurin.25.JDK` (winget есть).

## build.gradle

```gradle
dependencies {
    testImplementation(
            "com.codeborne:selenide:7.18.2",
            "org.junit.jupiter:junit-jupiter:6.1.3",
            "io.qameta.allure:allure-jupiter:3.1.1",
            "io.qameta.allure:allure-selenide:3.1.1")
    testRuntimeOnly "org.junit.platform:junit-platform-launcher"
    testRuntimeOnly "org.aspectj:aspectjweaver:1.9.27"
}

test {
    useJUnitPlatform()
    systemProperty "junit.jupiter.extensions.autodetection.enabled", "true"  // AllureJupiter из META-INF/services
    jvmArgs "-javaagent:${configurations.testRuntimeClasspath.find { it.name.startsWith('aspectjweaver') }}"
    doFirst { delete "allure-results" }                                      // чистый прогон — старое не смешивается
    // существующие systemProperty baseUrl/browser/browserSize/headless — без изменений
}
```

## TestBase — вложения при падении (дефолты AllureSelenide: screenshot + page source)

```java
@BeforeEach: SelenideLogger.addListener("AllureSelenide", new AllureSelenide());
@AfterEach:  closeWebDriver(); SelenideLogger.removeListener("AllureSelenide");
```

Если на контролируемом падении дефолты не приложат вложения — явно включить билдер-флаги `allure-selenide` 3.1.1 (имена методов сверить по классу), дефолт не предполагаем вслепую.

## SearchTests — шаги @Step (локаторы, assertions и порядок — без изменений)

Тело тестов остаётся проверкой; действия выносятся в `private static @Step`-хелперы, селекторы внутри — те же строки:

```java
@Step("Открыть поиск GitHub")
private static void openSearch() { open("/search"); }

@Step("Искать \"{0}\"")
private static void searchFor(String query) { $("[aria-label='Search GitHub']").setValue(query).pressEnter(); }

@Step("Открыть репозиторий \"{0}\" из выдачи")
private static void openRepositoryFromResults(String href) { $("[data-testid='results-list'] a[href='" + href + "']").click(); }

@Step("Открыть заведомо пустой поиск")
private static void openEmptyQuery() { open("/search?q=stars%3A%3C0&type=repositories"); }
```

Проверки (`shouldHave`, `webdriver().shouldHave(...)`, `shouldNot(exist)`) остаются в тестах в исходном порядке. Итого шаги в отчёте: именованные @Step + вложенные селенид-действия (AllureSelenide пишет LogEvent'ы как шаги).

## .gitignore

Добавить `allure-results/` и `allure-report/`.

## Приёмка (по шагам)

1. **JDK** → `.\gradlew.bat test` зелёный (3 теста), в `allure-results/` JSON'ы прогона.
2. **Флаги CLI по факту**: `npx --yes allure@3.33.0 --help`, `generate --help`, `open --help` → зафиксировать точный синтаксис.
3. **Зелёный отчёт**: `npx --yes allure@3.33.0 generate allure-results` → `allure-report/`; `npx --yes allure@3.33.0 open allure-report` как background_process → браузер; в отчёте **3 passed, видны именованные шаги**.
4. **Контролируемое падение**: временно ожидаемый текст теста 1 → `"NO-SUCH-REPO"`; `gradlew test` (падает; `doFirst delete` уже убрал старый прогон → в отчёте только текущий). generate + open: статус failed, **причина (assertion message/traces), упавший шаг красным, вложения screenshot + page source**.
5. **Откат**: вернуть `"QA.GURU"` (assertion восстановлен), финальный зелёный прогон, regenerate, open — 3 passed.
6. Проверка «нет смешивания»: в отчётеcontrolled-failure ровно 3 теста текущего прогона (1 failed), без «призраков».

## Риски / оговорки

- Сеть: нужны mavenCentral, npmjs, adoptium, github.com (тесты ходят на реальный GitHub).
- `allure open` — блокирующий сервер → только через `background_process`, закрытие по `stop`.
- `headless=false` (текущий дефолт) — окно Chrome реально открывается.
- Если AspectJ 1.9.27 откажется ткать Java 25 bytecode (weaving-ошибки в логе) — согласованный запасной путь: программный `Allure.step` без агента.
- Результаты: `allure-results/` в корне проекта (дефолт и allure-java, и автопоиска Allure 3 CLI).