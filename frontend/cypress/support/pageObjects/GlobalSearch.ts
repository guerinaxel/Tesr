export class GlobalSearch {
  typeQuery(value: string) {
    cy.get('[data-cy="global-search-input"]').type(value);
    return this;
  }

  expectResultInGroup(group: 'topics' | 'questions' | 'answers', text: string) {
    cy.get(`[data-cy="global-search-group-${group}"]`).contains(text).should('exist');
    return this;
  }

  expectMoreButton(group: 'topics' | 'questions' | 'answers', exists = true) {
    const assertion = exists ? 'exist' : 'not.exist';
    cy.get(`[data-cy="global-search-more-${group}"]`).should(assertion);
    return this;
  }

  clickMore(group: 'topics' | 'questions' | 'answers') {
    cy.get(`[data-cy="global-search-more-${group}"]`).click();
    return this;
  }
}
