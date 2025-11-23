const apiUrl = 'http://localhost:8000/api';

describe('AI Code Assistant app', () => {
  it('sends a chat message and renders assistant reply', () => {
    cy.intercept('POST', `${apiUrl}/code-qa/`, (req) => {
      expect(req.body).to.deep.equal({
        question: 'Bonjour, aide-moi !',
        system_prompt: 'code expert',
      });

      req.reply({
        statusCode: 200,
        body: { answer: 'Voici une réponse utile.' },
      });
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

  it('allows selecting a custom system prompt and sends it to the API', () => {
    cy.intercept('POST', `${apiUrl}/code-qa/`, (req) => {
      expect(req.body).to.deep.equal({
        question: 'Salut, explique-moi ceci.',
        system_prompt: 'custom',
        custom_prompt: 'Parle en français',
      });

      req.reply({ statusCode: 200, body: { answer: 'Réponse sur mesure.' } });
    }).as('sendCustom');

    cy.visit('/');

    cy.get('[data-cy="system-prompt-select"]').click();
    cy.get('mat-option').contains('custom').click();
    cy.get('[data-cy="custom-prompt-input"]').should('be.visible').type('Parle en français');

    cy.get('[data-cy="question-input"]').type('Salut, explique-moi ceci.');
    cy.get('[data-cy="send-button"]').click();

    cy.wait('@sendCustom');
    cy.get('.message--assistant .message__content').should('contain', 'Réponse sur mesure.');
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
