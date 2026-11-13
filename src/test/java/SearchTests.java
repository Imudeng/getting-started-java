import io.qameta.allure.Step;
import org.junit.jupiter.api.Test;

import static com.codeborne.selenide.Condition.exist;
import static com.codeborne.selenide.Condition.text;
import static com.codeborne.selenide.Selenide.$;
import static com.codeborne.selenide.Selenide.open;
import static com.codeborne.selenide.Selenide.webdriver;
import static com.codeborne.selenide.WebDriverConditions.url;
import static com.codeborne.selenide.WebDriverConditions.urlContaining;

public class SearchTests extends TestBase {
    @Test
    void successfulSearchTest() {
        openSearch();
        searchFor("qa.guru");
        $("[data-testid='results-list']").shouldHave(text("QA.GURU"));
    }

    @Test
    void openRepositoryFromSearchResults() {
        openSearch();
        searchFor("qa.guru");
        webdriver().shouldHave(urlContaining("q=qa.guru&type=repositories"));
        openRepositoryFromResults("/qa-guru/niffler");
        webdriver().shouldHave(url("https://github.com/qa-guru/niffler"));
    }

    @Test
    void emptyStateForImpossibleQuery() {
        openEmptyQuery();
        $("body").shouldHave(text("Your search did not match any repositories"));
        $("[data-testid='results-list']").shouldNot(exist);
    }

    @Step("Открыть поиск GitHub")
    private static void openSearch() {
        open("/search");
    }

    @Step("Искать \"{0}\"")
    private static void searchFor(String query) {
        $("[aria-label='Search GitHub']").setValue(query).pressEnter();
    }

    @Step("Перейти в \"{0}\" из выдачи")
    private static void openRepositoryFromResults(String href) {
        $("[data-testid='results-list'] a[href='" + href + "']").click();
    }

    @Step("Открыть заведомо пустой поиск")
    private static void openEmptyQuery() {
        open("/search?q=stars%3A%3C0&type=repositories");
    }
}