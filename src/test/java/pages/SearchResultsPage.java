package pages;

import com.codeborne.selenide.Selenide;
import com.codeborne.selenide.SelenideElement;
import io.qameta.allure.Step;

import static com.codeborne.selenide.Condition.exist;
import static com.codeborne.selenide.Condition.text;
import static com.codeborne.selenide.Selenide.$;
import static com.codeborne.selenide.Selenide.webdriver;
import static com.codeborne.selenide.WebDriverConditions.urlContaining;

public class SearchResultsPage {
    private final SelenideElement resultsList = $("[data-testid='results-list']");

    @Step("Открыть заведомо пустой поиск")
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

    @Step("Перейти в \"{0}\" из выдачи")
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