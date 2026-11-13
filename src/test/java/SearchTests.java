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
        open("/search");
        $("[aria-label='Search GitHub']").setValue("qa.guru").pressEnter();
        $("[data-testid='results-list']").shouldHave(text("QA.GURU"));
    }

    @Test
    void openRepositoryFromSearchResults() {
        open("/search");
        $("[aria-label='Search GitHub']").setValue("qa.guru").pressEnter();
        webdriver().shouldHave(urlContaining("q=qa.guru&type=repositories"));
        $("[data-testid='results-list'] a[href='/qa-guru/niffler']").click();
        webdriver().shouldHave(url("https://github.com/qa-guru/niffler"));
    }

    @Test
    void emptyStateForImpossibleQuery() {
        open("/search?q=stars%3A%3C0&type=repositories");
        $("body").shouldHave(text("Your search did not match any repositories"));
        $("[data-testid='results-list']").shouldNot(exist);
    }
}
