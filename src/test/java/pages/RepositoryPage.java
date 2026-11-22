package pages;

import static com.codeborne.selenide.Selenide.webdriver;
import static com.codeborne.selenide.WebDriverConditions.url;

public class RepositoryPage {
    public RepositoryPage shouldBeAt(String expectedUrl) {
        webdriver().shouldHave(url(expectedUrl));
        return this;
    }
}