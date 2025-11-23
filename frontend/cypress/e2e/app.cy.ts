const apiUrl = 'http://localhost:8000/api';

const stubTopicList = (topics: Array<{ id: number; name: string; message_count: number }>) => {
  cy.intercept('GET', `${apiUrl}/topics/`, { topics }).as('listTopics');
};

const stubTopicDetail = (topic: {
  id: number;
  name: string;
  message_count: number;
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}) => {
  cy.intercept('GET', `${apiUrl}/topics/${topic.id}/`, topic).as('topicDetail');
};

describe('AI Code Assistant app', () => {
  it('sends a chat message and renders assistant reply', () => {
    stubTopicList([{ id: 1, name: 'Sprint 12', message_count: 0 }]);
    stubTopicDetail({ id: 1, name: 'Sprint 12', message_count: 0, messages: [] });

    cy.intercept('POST', `${apiUrl}/code-qa/`, (req) => {
      expect(req.body).to.deep.equal({
        question: 'Bonjour, aide-moi !',
        system_prompt: 'code expert',
        topic_id: '1',
      });

      req.reply({
        statusCode: 200,
        body: { answer: 'Voici une réponse utile.' },
      });
    }).as('sendQuestion');

    cy.visit('/');
    cy.wait('@listTopics');
    cy.wait('@topicDetail');

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
    stubTopicList([{ id: 2, name: 'Docs', message_count: 0 }]);
    stubTopicDetail({ id: 2, name: 'Docs', message_count: 0, messages: [] });

    cy.intercept('POST', `${apiUrl}/code-qa/`, (req) => {
      expect(req.body).to.deep.equal({
        question: 'Salut, explique-moi ceci.',
        system_prompt: 'custom',
        custom_prompt: 'Parle en français',
        topic_id: '2',
      });

      req.reply({ statusCode: 200, body: { answer: 'Réponse sur mesure.' } });
    }).as('sendCustom');

    cy.visit('/');
    cy.wait('@listTopics');
    cy.wait('@topicDetail');

    cy.get('[data-cy="system-prompt-select"]').click();
    cy.get('mat-option').contains('custom').click();
    cy.get('[data-cy="custom-prompt-input"]').should('be.visible').type('Parle en français');

    cy.get('[data-cy="question-input"]').type('Salut, explique-moi ceci.');
    cy.get('[data-cy="send-button"]').click();

    cy.wait('@sendCustom');
    cy.get('.message--assistant .message__content').should('contain', 'Réponse sur mesure.');
  });

  it('creates a new topic and shows its empty conversation state', () => {
    stubTopicList([]);
    cy.intercept('POST', `${apiUrl}/topics/`, {
      id: 3,
      name: 'New thread',
      message_count: 0,
      messages: [],
    }).as('createTopic');
    stubTopicDetail({ id: 3, name: 'New thread', message_count: 0, messages: [] });

    cy.visit('/');
    cy.wait('@listTopics');

    cy.get('[data-cy="new-topic-input"]').type('New thread');
    cy.get('[data-cy="create-topic-button"]').click();

    cy.wait('@createTopic');
    cy.wait('@topicDetail');

    cy.contains('[data-cy="topic-item"]', 'New thread').should('have.class', 'selected');
    cy.get('[data-cy="empty-state"]').should('contain', 'Commencez la conversation');
  });

  it('navigates to the Build RAG page and triggers an index build', () => {
    stubTopicList([]);

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
