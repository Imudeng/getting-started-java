import com.codeborne.selenide.Configuration;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

import static com.codeborne.selenide.Selenide.closeWebDriver;

public class TestBase {
    @BeforeEach
    void startBrowser() {
        Configuration.baseUrl = System.getProperty("baseUrl");
        Configuration.browser = System.getProperty("browser");
        Configuration.browserSize = System.getProperty("browserSize");
        Configuration.headless = Boolean.parseBoolean(System.getProperty("headless"));
    }

    @AfterEach
    void stopBrowser() {
        closeWebDriver();
    }
}