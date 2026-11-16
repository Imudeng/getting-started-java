# Рефакторинг GitHub search-тестов: page objects + fluent API

> **Статус (16.11):** реализовано (этим коммитом) — `pages/SearchPage`, `pages/SearchResultsPage`, `pages/RepositoryPage`; `TestBase` и `SearchTests` перенесены в пакет `tests` (содержимое TestBase 1:1); тесты — только fluent-вызовы. Прогон `gradlew test -Dheadless=true`: 3/3 зелёные, `tests.SearchTests`, именованные шаги Allure сохранены.
> **Ограничения:** прогон только headless (GUI-сессия недоступна в рабочей среде); `@Step` перенесены на методы-действия page objects — в образцах кода плана их не было, иначе регрессия именованных шагов Фазы 4 (тексты шагов совпадают с HEAD; аргумент «Перейти в…» — теперь полное имя репо без ведущего `/`).

## Согласованный стиль

- **Fluent API**: методы действий возвращают следующий page object (`searchFor → SearchResultsPage`, `openRepository → RepositoryPage`), should-методы возвращают `this`.
- **Проверки только в should…-методах страниц**, включая `webdriver()`-проверки URL (решение пользователя).
- **`private final SelenideElement`-поля**, инициализация ленивым `$()` при создании объекта (DOM не трогается до первого действия — семантика идентична).
- **Имена методов — действия пользователя**: `open`, `searchFor`, `openRepository`; проверки — `shouldHaveResult`, `shouldBeEmpty`, `shouldDisplayResultsFor`, `shouldBeAt`.
- **Компоненты не заводятся**: повторяющихся блоков нет; `results-list` принадлежит SearchResultsPage.
- **Локаторы, assertions и порядок проверок — без изменений** (ссылка репо параметризована по решению пользователя: форма селектора идентична).

## Структура файлов

```
src/test/java/
├── pages/SearchPage.java          (новый)
├── pages/SearchResultsPage.java   (новый)
├── pages/RepositoryPage.java      (новый, минимальный — для url-проверки после клика)
├── tests/TestBase.java            (перенос из default package, содержимое 1:1 + package)
├── tests/SearchTests.java         (перенос, только fluent-вызовы)
├── SearchTests.java               (удалить)
└── TestBase.java                  (удалить)
```

TestBase обязан переехать в пакет: класс из default package недоступен импорту из `tests`.

## Код

### pages/SearchPage.java

```java
package pages;

import com.codeborne.selenide.Selenide;
import com.codeborne.selenide.SelenideElement;

import static com.codeborne.selenide.Selenide.$;

public class SearchPage {
    private final SelenideElement searchField = $("[aria-label='Search GitHub']");

    public SearchPage open() {
        Selenide.open("/search");
        return this;
    }

    public SearchResultsPage searchFor(String query) {
        searchField.setValue(query).pressEnter();
        return new SearchResultsPage();
    }
}
```

### pages/SearchResultsPage.java

```java
package pages;

import com.codeborne.selenide.Selenide;
import com.codeborne.selenide.SelenideElement;

import static com.codeborne.selenide.Condition.exist;
import static com.codeborne.selenide.Condition.text;
import static com.codeborne.selenide.Selenide.$;
import static com.codeborne.selenide.Selenide.webdriver;
import static com.codeborne.selenide.WebDriverConditions.urlContaining;

public class SearchResultsPage {
    private final SelenideElement resultsList = $("[data-testid='results-list']");

    public SearchResultsPage openForQuery(String encodedQuery) {
        Selenide.open("/search?q=" + encodedQuery + "&type=repositories");
        return this;
    }

    public SearchResultsPage shouldHaveResult(String expectedText) {
        resultsList.shouldHave(text(expectedText));
        return this;
    }

    public SearchResultsPage shouldDisplayResultsFor(String query) {
        webdriver().shouldHave(urlContaining("q=" + query + "&type=repositories"));
        return this;
    }

    public RepositoryPage openRepository(String repoFullName) {
        $("[data-testid='results-list'] a[href='/" + repoFullName + "']").click();
        return new RepositoryPage();
    }

    public SearchResultsPage shouldBeEmpty() {
        $("body").shouldHave(text("Your search did not match any repositories"));
        resultsList.shouldNot(exist);
        return this;
    }
}
```

### pages/RepositoryPage.java

```java
package pages;

import static com.codeborne.selenide.Selenide.webdriver;
import static com.codeborne.selenide.WebDriverConditions.url;

public class RepositoryPage {
    public RepositoryPage shouldBeAt(String expectedUrl) {
        webdriver().shouldHave(url(expectedUrl));
        return this;
    }
}
```

### tests/SearchTests.java

```java
package tests;

import org.junit.jupiter.api.Test;
import pages.SearchPage;
import pages.SearchResultsPage;

public class SearchTests extends TestBase {
    @Test
    void successfulSearchTest() {
        new SearchPage().open()
                .searchFor("qa.guru")
                .shouldHaveResult("QA.GURU");
    }

    @Test
    void openRepositoryFromSearchResults() {
        new SearchPage().open()
                .searchFor("qa.guru")
                .shouldDisplayResultsFor("qa.guru")
                .openRepository("qa-guru/niffler")
                .shouldBeAt("https://github.com/qa-guru/niffler");
    }

    @Test
    void emptyStateForImpossibleQuery() {
        new SearchResultsPage().openForQuery("stars%3A%3C0")
                .shouldBeEmpty();
    }
}
```

`tests/TestBase.java` — текущее содержимое без изменений, только `package tests;`.

## Проверка «семантика идентична HEAD»

| Тест | HEAD | После |
|---|---|---|
| 1 | `open("/search")` → `setValue("qa.guru").pressEnter()` → `results-list shouldHave text("QA.GURU")` | те же селекторы/условия/порядок |
| 2 | …→ `urlContaining("q=qa.guru&type=repositories")` → клик `a[href='/qa-guru/niffler']` → `url("https://github.com/qa-guru/niffler")` | те же, селектор ссылки собран из параметра в той же форме |
| 3 | `open("/search?q=stars%3A%3C0&type=repositories")` → body text → results-list shouldNot(exist) | URL-строка совпадает посимвольно, порядок проверок тот же |

## Верификация

1. `.\gradlew.bat test` — все 3 теста зелёные (JDK 25 через foojay-toolchain, gradle 9.8.1 уже в кэше; требует сети к github.com и gradle plugin portal).
2. При недоступности GUI-сессии в песочнице — повторить с `-Dheadless=true` и явно это указать.
3. `git diff HEAD -- src/test/java` — убедиться, что изменены только файлы теста, локаторы/условия/порядок не задеты.

## Ограничения

- `headless=false` по умолчанию — откроется окно Chrome.
- Пакет `pages` — рядом с `tests` в `src/test/java`, отдельного main-исходника нет (библиотечный плагин `java-library`, тестовый код остаётся в test source set).