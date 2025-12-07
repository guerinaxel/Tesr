import { ChatPage } from '../../support/pageObjects/ChatPage';
import { TopicsPanel } from '../../support/pageObjects/TopicsPanel';
import {
  apiUrl,
  stubCreateTopic,
  stubRagSources,
  stubStreamQuestion,
  stubTopicDetail,
  stubTopicList,
} from '../../support/utils/apiStubs';

const chatPage = new ChatPage();
const topicsPanel = new TopicsPanel();

const defaultSources = [
  {
    id: 'source-1',
    name: 'Backend',
    description: 'Django code',
    path: '/tmp/backend',
    created_at: new Date().toISOString(),
    total_files: 10,
    total_chunks: 20,
  },
  {
    id: 'source-2',
    name: 'Frontend',
    description: 'Angular UI',
    path: '/tmp/frontend',
    created_at: new Date().toISOString(),
    total_files: 15,
    total_chunks: 25,
  },
];

describe('Chat / multi-source flows', () => {
  it('sends a chat message and renders assistant reply', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([{ id: 1, name: 'Sprint 12', message_count: 0 }]);
    stubTopicDetail({ id: 1, name: 'Sprint 12', message_count: 0, messages: [] });
    stubStreamQuestion(
      {
        question: 'Bonjour, aide-moi !',
        system_prompt: 'code expert',
        topic_id: 1,
        sources: [defaultSources[0].id],
      },
      [
        { event: 'meta', data: { num_contexts: 1 } },
        { event: 'token', data: 'Voici une ' },
        { event: 'done', data: { answer: 'Voici une réponse utile.' } },
      ]
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();
    chatPage.typeQuestion('Bonjour, aide-moi !').clickSend();

    // Assert
    cy.get('@streamQuestion');
    chatPage
      .expectSendEnabled()
      .expectUserMessageContains('Bonjour, aide-moi !')
      .expectAssistantMessageContains('Voici une réponse utile.')
      .expectAssistantMessageCount(1);
  });

  it('creates a topic from the first message and sends with Enter', () => {
    // Arrange
    const question = 'Nouvelle exploration du module paiement';
    const expectedTopic = `${question}`;

    stubRagSources([defaultSources[0]]);
    stubTopicList([]);
    cy.intercept('POST', `${apiUrl}/topics/`, (req) => {
      expect(req.body).to.deep.equal({ name: expectedTopic });
      req.reply({ id: 4, name: expectedTopic, message_count: 0, messages: [], next_offset: null });
    }).as('createTopic');
    stubTopicDetail({ id: 4, name: expectedTopic, message_count: 1, messages: [] });
    stubStreamQuestion(
      { question, system_prompt: 'code expert', topic_id: 4, sources: [defaultSources[0].id] },
      [
        { event: 'token', data: 'Réponse en ' },
        { event: 'done', data: { answer: 'Réponse en cours.' } },
      ],
      'streamNewTopic'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList();
    chatPage.typeQuestionWithEnter(question);

    // Assert
    cy.get('@createTopic');
    cy.get('@streamNewTopic');
    topicsPanel.expectTopicSelected(expectedTopic);
    chatPage.expectAssistantMessageContains('Réponse en cours.');
  });

  it('selects multiple RAG sources and shows used sources in chat', () => {
    // Arrange
    cy.intercept('POST', '**/code-qa/**').as('anyQa');
    stubRagSources(defaultSources);
    stubTopicList([{ id: 7, name: 'Multi RAG', message_count: 0 }]);
    stubTopicDetail({ id: 7, name: 'Multi RAG', message_count: 0, messages: [] });
    stubStreamQuestion(
      {
        question: 'Quel code est impacté ?',
        system_prompt: 'code expert',
        topic_id: 7,
        sources: [defaultSources[0].id, defaultSources[1].id],
      },
      [
        { event: 'meta', data: { source_names: ['Backend', 'Frontend'], contexts: [] } },
        { event: 'done', data: { answer: 'Réponse combinée.' } },
      ],
      'multiSourceStream'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();
    cy.wait('@ragSources');
    cy.window().its('chatComponent').then((cmp: any) => {
      cmp.selectedSources.set([defaultSources[0].id, defaultSources[1].id]);
    });
    cy.window().its('chatComponent').then((cmp: any) => {
      cmp.selectedSources.set([defaultSources[0].id, defaultSources[1].id]);
      cmp.question.set('Quel code est impacté ?');
      cmp.selectedTopicId.set(7);
      cmp.onSubmit();
    });

    // Assert
    cy.wait('@multiSourceStream')
      .its('request.body.sources')
      .should('deep.equal', [defaultSources[0].id, defaultSources[1].id]);
    chatPage.expectAssistantMessageContains('Réponse combinée.');
    cy.get('[data-cy="sources-used-banner"]').should('contain', 'Backend').and('contain', 'Frontend');
  });
});
