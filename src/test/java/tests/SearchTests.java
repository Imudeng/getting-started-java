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