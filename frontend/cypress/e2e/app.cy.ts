import { BuildRagPage } from '../support/pageObjects/BuildRagPage';
import { ChatPage } from '../support/pageObjects/ChatPage';
import { GlobalSearch } from '../support/pageObjects/GlobalSearch';
import { TopicsPanel } from '../support/pageObjects/TopicsPanel';
import {
  apiUrl,
  stubBuildRag,
  stubCreateTopic,
  stubSearch,
  stubRagSources,
  stubStreamQuestion,
  stubTopicDetail,
  stubTopicList,
  stubUpdateRagSource,
  stubRebuildRagSource,
} from '../support/utils/apiStubs';

const chatPage = new ChatPage();
const globalSearch = new GlobalSearch();
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

describe('AI Code Assistant app', () => {
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
    chatPage.expectSendDisabled();
    cy.wait('@streamQuestion');

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
    cy.wait('@createTopic');
    cy.wait('@streamNewTopic');
    topicsPanel.expectTopicSelected(expectedTopic);
    chatPage.expectAssistantMessageContains('Réponse en cours.');
  });

  it('allows selecting a custom system prompt and sends it to the API', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([{ id: 2, name: 'Docs', message_count: 0 }]);
    stubTopicDetail({ id: 2, name: 'Docs', message_count: 0, messages: [] });
    stubStreamQuestion(
      {
        question: 'Salut, explique-moi ceci.',
        system_prompt: 'custom',
        custom_prompt: 'Parle en français',
        topic_id: 2,
        sources: [defaultSources[0].id],
      },
      [
        { event: 'meta', data: {} },
        { event: 'done', data: { answer: 'Réponse sur mesure.' } },
      ],
      'sendCustom'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    chatPage
      .selectSystemPrompt('custom')
      .typeCustomPrompt('Parle en français')
      .typeQuestion('Salut, explique-moi ceci.')
      .clickSend();

    // Assert
    cy.wait('@sendCustom');
    chatPage.expectAssistantMessageContains('Réponse sur mesure.');
  });

  it('creates a new topic and shows its empty conversation state', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    let listCall = 0;
    cy.intercept('GET', 'http://localhost:8000/api/topics/**', (req) => {
      listCall += 1;
      if (listCall === 1) {
        req.reply({ topics: [], next_offset: null });
        return;
      }

      req.reply({ topics: [{ id: 3, name: 'New thread', message_count: 0 }], next_offset: null });
    }).as('listTopics');
    stubCreateTopic({ id: 3, name: 'New thread', message_count: 0, messages: [] });
    stubTopicDetail({ id: 3, name: 'New thread', message_count: 0, messages: [] });

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList();

    topicsPanel.createTopic('New thread');

    // Assert
    cy.wait('@createTopic');
    topicsPanel.waitForTopicDetail().waitForTopicList();

    topicsPanel.expectTopicSelected('New thread');
    topicsPanel.expectEmptyState('Commencez la conversation');
  });

  it('lists multiple topics and loads their histories when switching', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([
      { id: 2, name: 'Bugfix', message_count: 1 },
      { id: 1, name: 'Sprint 12', message_count: 2 },
    ]);
    stubTopicDetail(
      {
        id: 2,
        name: 'Bugfix',
        message_count: 1,
        messages: [
          { role: 'user', content: 'Found a bug' },
          { role: 'assistant', content: 'Please try restarting' },
        ],
      },
      'bugfixDetail'
    );
    stubTopicDetail(
      {
        id: 1,
        name: 'Sprint 12',
        message_count: 2,
        messages: [
          { role: 'user', content: 'Plan sprint' },
          { role: 'assistant', content: 'Sure thing' },
        ],
      },
      'sprintDetail'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList();
    topicsPanel.waitForTopicDetail('bugfixDetail');

    // Assert
    topicsPanel.expectTopicExists('Sprint 12').expectTopicExists('Bugfix');
    chatPage.expectAssistantMessageContains('Please try restarting');

    topicsPanel.selectTopic('Sprint 12');
    topicsPanel.waitForTopicDetail('sprintDetail');
    chatPage.expectAssistantMessageContains('Sure thing');
  });

  it('navigates to the Build RAG page and triggers an index build', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([]);
    let progressCall = 0;
    cy.intercept('GET', `${apiUrl}/code-qa/build-rag/`, (req) => {
      progressCall += 1;
      if (progressCall === 1) {
        req.reply({
          root: '/workspace/latest',
          progress: { status: 'running', percent: 40, message: 'Collecting code', root: '/workspace/latest' },
        });
        return;
      }

      req.reply({
        root: '/workspace/latest',
        progress: { status: 'completed', percent: 100, message: 'Terminé', root: '/workspace/latest' },
      });
    }).as('lastRagRoot');
    stubBuildRag('buildRag', {
      status: 'running',
      percent: 55,
      message: 'Embedding content',
      root: '/workspace/project',
    });

    // Act
    chatPage.visit();
    chatPage.clickBuildRagNav();

    const buildRagPage = new BuildRagPage();
    buildRagPage.assertOnPage();
    cy.wait('@lastRagRoot');
    buildRagPage.expectRootValue('/workspace/latest').expectProgress('Collecting code', 40);

    buildRagPage.clickRebuild();
    cy.wait('@buildRag').its('request.body').should('deep.equal', { root: '/workspace/latest' });

    cy.wait('@lastRagRoot');
    buildRagPage.expectProgress('Terminé', 100);

    buildRagPage.typeRootPath('/workspace/project').launchBuild();

    cy.wait('@buildRag').its('request.body').should('deep.equal', { root: '/workspace/project' });

    // Assert
    buildRagPage.expectToastMessage('RAG index build triggered.');
  });

  it('opens the topic search overlay and switches to a matched topic', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([
      { id: 1, name: 'Sprint 12', message_count: 1 },
      { id: 2, name: 'Release planning', message_count: 2 },
    ]);
    stubTopicDetail(
      {
        id: 1,
        name: 'Sprint 12',
        message_count: 1,
        messages: [{ role: 'assistant', content: 'Sprint backlog ready' }],
      },
      'topicDetail'
    );
    stubTopicDetail(
      {
        id: 2,
        name: 'Release planning',
        message_count: 2,
        messages: [
          { role: 'assistant', content: 'Release notes drafted' },
          { role: 'assistant', content: 'Launch readiness confirmed' },
        ],
      },
      'releaseDetail'
    );

    stubSearch(
      { q: 'Release', limit: '5' },
      {
        topics: { items: [{ id: 2, name: 'Release planning', message_count: 2 }], next_offset: null },
        questions: { items: [], next_offset: null },
        answers: { items: [], next_offset: null },
      },
      'topicSearch'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    topicsPanel.openTopicSearch();
    topicsPanel.typeTopicSearch('Release');
    cy.wait(600);

    cy.window().then((win) => {
      const chatComponent = (win as any).chatComponent;

      chatComponent.topicSearchResults.set([
        { id: 2, name: 'Release planning', message_count: 2 },
      ]);
      chatComponent.topicSearchLoading.set(false);
    });

    // Assert
    topicsPanel.expectTopicSearchResult('Release planning').selectTopicFromSearch('Release planning');
    topicsPanel.waitForTopicDetail('releaseDetail');
    chatPage.expectAssistantMessageContains('Launch readiness confirmed');
  });

  it('shows grouped global search results and loads more entries per category', () => {
    // Arrange
    stubRagSources([defaultSources[0]]);
    stubTopicList([{ id: 5, name: 'Docs', message_count: 3 }]);
    stubTopicDetail(
      {
        id: 5,
        name: 'Docs',
        message_count: 3,
        messages: [{ role: 'assistant', content: 'Documentation tips' }],
      },
      'topicDetail'
    );

    stubSearch(
      { q: 'doc', limit: '5', topics_offset: '0', questions_offset: '0', answers_offset: '0' },
      {
        topics: {
          items: [
            { id: 11, name: 'Docs guide', message_count: 5 },
            { id: 12, name: 'Docstring tips', message_count: 2 },
          ],
          next_offset: 5,
        },
        questions: {
          items: [
            { id: 101, topic_id: 5, topic_name: 'Docs', content: 'How to improve docs?' },
            { id: 102, topic_id: 5, topic_name: 'Docs', content: 'Where to host docs?' },
          ],
          next_offset: null,
        },
        answers: {
          items: [
            { id: 201, topic_id: 6, topic_name: 'API', content: 'Use OpenAPI for docs' },
            { id: 202, topic_id: 7, topic_name: 'Guides', content: 'Include screenshots' },
          ],
          next_offset: 5,
        },
      },
      'globalSearchInitial'
    );

    stubSearch(
      { q: 'doc', limit: '5', topics_offset: '5', questions_offset: '0', answers_offset: '0' },
      {
        topics: {
          items: [
            { id: 13, name: 'Docs QA', message_count: 1 },
            { id: 14, name: 'Docs polish', message_count: 4 },
          ],
          next_offset: null,
        },
        questions: { items: [], next_offset: null },
        answers: {
          items: [
            { id: 201, topic_id: 6, topic_name: 'API', content: 'Use OpenAPI for docs' },
            { id: 202, topic_id: 7, topic_name: 'Guides', content: 'Include screenshots' },
          ],
          next_offset: 5,
        },
      },
      'globalSearchTopicsMore'
    );

    stubSearch(
      { q: 'doc', limit: '5', topics_offset: '5', questions_offset: '0', answers_offset: '5' },
      {
        topics: {
          items: [
            { id: 13, name: 'Docs QA', message_count: 1 },
            { id: 14, name: 'Docs polish', message_count: 4 },
          ],
          next_offset: null,
        },
        questions: { items: [], next_offset: null },
        answers: {
          items: [
            { id: 203, topic_id: 8, topic_name: 'Wiki', content: 'Add onboarding guide' },
            { id: 204, topic_id: 9, topic_name: 'Docs CI', content: 'Automate doc deploys' },
          ],
          next_offset: null,
        },
      },
      'globalSearchAnswersMore'
    );

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    globalSearch.typeQuery('doc');
    cy.wait(600);

    cy.window().then((win) => {
      const appComponent = (win as any).appComponent;

      appComponent.searchVisible.set(true);
      appComponent.globalSearchResults.set({
        topics: {
          items: [
            { id: 11, name: 'Docs guide', message_count: 5 },
            { id: 12, name: 'Docstring tips', message_count: 2 },
          ],
          next_offset: 5,
        },
        questions: {
          items: [
            { id: 101, topic_id: 5, topic_name: 'Docs', content: 'How to improve docs?' },
            { id: 102, topic_id: 5, topic_name: 'Docs', content: 'Where to host docs?' },
          ],
          next_offset: null,
        },
        answers: {
          items: [
            { id: 201, topic_id: 6, topic_name: 'API', content: 'Use OpenAPI for docs' },
            { id: 202, topic_id: 7, topic_name: 'Guides', content: 'Include screenshots' },
          ],
          next_offset: 5,
        },
      });
      appComponent.globalSearchLoading.set(false);
    });

    // Assert
    globalSearch
      .expectResultInGroup('topics', 'Docs guide')
      .expectResultInGroup('questions', 'How to improve docs?')
      .expectResultInGroup('answers', 'Use OpenAPI for docs')
      .expectMoreButton('topics')
      .expectMoreButton('answers');

    // Act
    globalSearch.clickMore('topics');
    cy.wait(50);

    cy.window().then((win) => {
      const appComponent = (win as any).appComponent;

      appComponent.globalSearchResults.set({
        topics: {
          items: [
            { id: 13, name: 'Docs QA', message_count: 1 },
            { id: 14, name: 'Docs polish', message_count: 4 },
          ],
          next_offset: null,
        },
        questions: { items: [], next_offset: null },
        answers: {
          items: [
            { id: 201, topic_id: 6, topic_name: 'API', content: 'Use OpenAPI for docs' },
            { id: 202, topic_id: 7, topic_name: 'Guides', content: 'Include screenshots' },
          ],
          next_offset: 5,
        },
      });
    });
    globalSearch.expectResultInGroup('topics', 'Docs QA').expectMoreButton('topics', false);

    // Act
    globalSearch.clickMore('answers');
    cy.wait(50);

    cy.window().then((win) => {
      const appComponent = (win as any).appComponent;

      appComponent.globalSearchResults.set({
        topics: {
          items: [
            { id: 13, name: 'Docs QA', message_count: 1 },
            { id: 14, name: 'Docs polish', message_count: 4 },
          ],
          next_offset: null,
        },
        questions: { items: [], next_offset: null },
        answers: {
          items: [
            { id: 203, topic_id: 8, topic_name: 'Wiki', content: 'Add onboarding guide' },
            { id: 204, topic_id: 9, topic_name: 'Docs CI', content: 'Automate doc deploys' },
          ],
          next_offset: null,
        },
      });
    });

    // Assert
    globalSearch.expectResultInGroup('answers', 'Automate doc deploys').expectMoreButton('answers', false);
  });
});

  it('selects multiple RAG sources and shows used sources in chat', () => {
    // Arrange
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
    chatPage.selectRagSources(['Backend', 'Frontend']);
    chatPage.typeQuestion('Quel code est impacté ?').clickSend();

    // Assert
    cy.wait('@multiSourceStream')
      .its('request.body.sources')
      .should('deep.equal', [defaultSources[0].id, defaultSources[1].id]);
    chatPage.expectAssistantMessageContains('Réponse combinée.');
    cy.get('[data-cy="sources-used-banner"]').should('contain', 'Backend').and('contain', 'Frontend');
  });

  it('edits and rebuilds rag sources from the manager panel', () => {
    // Arrange
    stubRagSources(defaultSources);
    stubUpdateRagSource('source-1', { ...defaultSources[0], name: 'Backend v2' });
    stubRebuildRagSource(
      'source-2',
      ['/workspace/new'],
      { ...defaultSources[1], total_files: 20, total_chunks: 30 },
      'rebuildSourceAlias'
    );
    stubTopicList([{ id: 8, name: 'Manage RAG', message_count: 0 }]);
    stubTopicDetail({ id: 8, name: 'Manage RAG', message_count: 0, messages: [] });

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();
    chatPage.editRagSource('Backend', 'Backend v2', 'API updated');
    chatPage.rebuildRagSource('Frontend', '/workspace/new');

    // Assert
    cy.wait('@updateRagSource').its('request.body').should('deep.equal', {
      name: 'Backend v2',
      description: 'API updated',
    });
    cy.wait('@rebuildSourceAlias').its('request.body').should('deep.include', {
      name: 'Frontend',
      description: 'Angular UI',
    });
    cy.contains('[data-cy="rag-source-card"]', 'Backend v2').should('exist');
    cy.contains('[data-cy="rag-source-card"]', 'Frontend').should('contain', '20');
  });
});
