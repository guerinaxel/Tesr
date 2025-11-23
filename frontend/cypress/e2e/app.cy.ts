const apiUrl = 'http://localhost:8000/api';

describe('AI Code Assistant app', () => {
  it('sends a chat message and renders assistant reply', () => {
    cy.intercept('POST', `${apiUrl}/code-qa/`, {
      statusCode: 200,
      body: { answer: 'Voici une réponse utile.' },
    }).as('sendQuestion');

    cy.visit('/');

    cy.get('[data-cy="empty-state"]', { timeout: 10000 }).should('be.visible');
    cy.get('[data-cy="question-input"]').type('Bonjour, aide-moi !');
    cy.get('[data-cy="send-button"]').click();

    cy.get('[data-cy="send-button"]').should('be.disabled');
    cy.wait('@sendQuestion');

    cy.get('[data-cy="send-button"]').should('not.be.disabled');
    cy.get('.message--user .message__content').should('contain', 'Bonjour, aide-moi !');
    cy.get('.message--assistant .message__content').should('contain', 'Voici une réponse utile.');
    cy.get('[data-cy="messages"]').find('.message--assistant').should('have.length', 1);
  });

  it('navigates to the Build RAG page and triggers an index build', () => {
    cy.intercept('POST', `${apiUrl}/code-qa/build-rag/`, (req) => {
      req.reply({ statusCode: 200, body: {} });
    }).as('buildRag');

    cy.visit('/');
    cy.get('[data-cy="build-rag-nav"]', { timeout: 10000 }).click();

    cy.url().should('include', '/build-rag');
    cy.get('[data-cy="root-input"]').type('/workspace/project');
    cy.get('[data-cy="launch-button"]').click();

    cy.wait('@buildRag').its('request.body').should('deep.equal', { root: '/workspace/project' });
    cy.get('[data-cy="toast"]').should('be.visible').and('contain', 'RAG index build triggered.');
  });
});
