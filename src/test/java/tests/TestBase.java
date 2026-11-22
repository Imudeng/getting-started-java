package tests;

import com.codeborne.selenide.Configuration;
import com.codeborne.selenide.logevents.SelenideLogger;
import io.qameta.allure.selenide.AllureSelenide;
import org.openqa.selenium.chrome.ChromeOptions;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

import java.util.Map;

import static com.codeborne.selenide.Selenide.closeWebDriver;

public class TestBase {
    @BeforeEach
    void startBrowser() {
        SelenideLogger.addListener("AllureSelenide", new AllureSelenide());
        Configuration.baseUrl = System.getProperty("baseUrl");
        Configuration.browser = System.getProperty("browser");
        Configuration.browserSize = System.getProperty("browserSize");
        Configuration.headless = Boolean.parseBoolean(System.getProperty("headless"));
        String remote = System.getProperty("remote");
        boolean remoteSet = remote != null && !remote.isBlank();
        if (Boolean.getBoolean("noSandbox") || remoteSet) {
            ChromeOptions options = new ChromeOptions();
            if (Boolean.getBoolean("noSandbox")) {
                options.addArguments("--no-sandbox", "--disable-dev-shm-usage");
            }
            if (remoteSet) {
                // как в зелёном демо курса: CDP-сокет Selenoid изнутри агентской сети недоступен
                options.setCapability("se:cdpEnabled", false);
                options.setCapability("selenoid:options", Map.of("enableVNC", true, "enableVideo", false));
            }
            Configuration.browserCapabilities = options;
        }
    }

    @AfterEach
    void stopBrowser() {
        closeWebDriver();
        SelenideLogger.removeListener("AllureSelenide");
    }
}