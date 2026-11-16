package pages;

import com.codeborne.selenide.Selenide;
import com.codeborne.selenide.SelenideElement;
import io.qameta.allure.Step;

import static com.codeborne.selenide.Selenide.$;

public class SearchPage {
    private final SelenideElement searchField = $("[aria-label='Search GitHub']");

    @Step("Открыть поиск GitHub")
    public SearchPage open() {
        Selenide.open("/search");
        return this;
    }

    @Step("Искать \"{0}\"")
    public SearchResultsPage searchFor(String query) {
        searchField.setValue(query).pressEnter();
        return new SearchResultsPage();
    }
}