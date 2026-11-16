package tests;

import com.codeborne.selenide.Configuration;
import com.codeborne.selenide.logevents.SelenideLogger;
import io.qameta.allure.selenide.AllureSelenide;
import org.openqa.selenium.chrome.ChromeOptions;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

import static com.codeborne.selenide.Selenide.closeWebDriver;

public class TestBase {
    @BeforeEach
    void startBrowser() {
        SelenideLogger.addListener("AllureSelenide", new AllureSelenide());
        Configuration.baseUrl = System.getProperty("baseUrl");
        Configuration.browser = System.getProperty("browser");
        Configuration.browserSize = System.getProperty("browserSize");
        Configuration.headless = Boolean.parseBoolean(System.getProperty("headless"));
        if (Boolean.getBoolean("noSandbox")) {
            Configuration.browserCapabilities = new ChromeOptions()
                    .addArguments("--no-sandbox", "--disable-dev-shm-usage");
        }
    }

    @AfterEach
    void stopBrowser() {
        closeWebDriver();
        SelenideLogger.removeListener("AllureSelenide");
    }
}