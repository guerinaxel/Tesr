export class TopicsPanel {
  waitForTopicList(alias = 'listTopics') {
    cy.wait(`@${alias}`);
    return this;
  }

  waitForTopicDetail(alias = 'topicDetail') {
    cy.wait(`@${alias}`);
    return this;
  }

  createTopic(name: string) {
    cy.get('[data-cy="new-topic-input"]').type(name);
    cy.get('[data-cy="create-topic-button"]').click();
    return this;
  }

  selectTopic(name: string) {
    cy.contains('[data-cy="topic-item"]', name).click();
    return this;
  }

  expectTopicSelected(name: string) {
    cy.contains('[data-cy="topic-item"]', name).should('have.class', 'selected');
    return this;
  }

  expectTopicExists(name: string) {
    cy.contains('[data-cy="topic-item"]', name).should('exist');
    return this;
  }

  expectEmptyState(text: string) {
    cy.get('[data-cy="empty-state"]').should('contain', text);
    return this;
  }

  openTopicSearch() {
    cy.get('[data-cy="topic-search-trigger"]').click();
    return this;
  }

  typeTopicSearch(term: string) {
    cy.get('[data-cy="topic-search-input"]').type(term);
    return this;
  }

  expectTopicSearchResult(name: string) {
    cy.get('[data-cy="topic-search-results"]').contains(name).should('exist');
    return this;
  }

  selectTopicFromSearch(name: string) {
    cy.get('[data-cy="topic-search-results"]').contains(name).click();
    return this;
  }
}
