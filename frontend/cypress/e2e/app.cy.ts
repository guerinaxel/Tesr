import { BuildRagPage } from '../support/pageObjects/BuildRagPage';
import { ChatPage } from '../support/pageObjects/ChatPage';
import { GlobalSearch } from '../support/pageObjects/GlobalSearch';
import { TopicsPanel } from '../support/pageObjects/TopicsPanel';
import {
  stubBuildRag,
  stubCreateTopic,
  stubSearch,
  stubSendQuestion,
  stubTopicDetail,
  stubTopicList,
} from '../support/utils/apiStubs';

const chatPage = new ChatPage();
const globalSearch = new GlobalSearch();
const topicsPanel = new TopicsPanel();

describe('AI Code Assistant app', () => {
  it('sends a chat message and renders assistant reply', () => {
    stubTopicList([{ id: 1, name: 'Sprint 12', message_count: 0 }]);
    stubTopicDetail({ id: 1, name: 'Sprint 12', message_count: 0, messages: [] });
    stubSendQuestion(
      {
        question: 'Bonjour, aide-moi !',
        system_prompt: 'code expert',
        topic_id: 1,
      },
      { answer: 'Voici une réponse utile.' }
    );

    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    chatPage.typeQuestion('Bonjour, aide-moi !').clickSend();

    chatPage.expectSendDisabled();
    cy.wait('@sendQuestion');

    chatPage
      .expectSendEnabled()
      .expectUserMessageContains('Bonjour, aide-moi !')
      .expectAssistantMessageContains('Voici une réponse utile.')
      .expectAssistantMessageCount(1);
  });

  it('allows selecting a custom system prompt and sends it to the API', () => {
    stubTopicList([{ id: 2, name: 'Docs', message_count: 0 }]);
    stubTopicDetail({ id: 2, name: 'Docs', message_count: 0, messages: [] });
    stubSendQuestion(
      {
        question: 'Salut, explique-moi ceci.',
        system_prompt: 'custom',
        custom_prompt: 'Parle en français',
        topic_id: 2,
      },
      { answer: 'Réponse sur mesure.' },
      'sendCustom'
    );

    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    chatPage
      .selectSystemPrompt('custom')
      .typeCustomPrompt('Parle en français')
      .typeQuestion('Salut, explique-moi ceci.')
      .clickSend();

    cy.wait('@sendCustom');
    chatPage.expectAssistantMessageContains('Réponse sur mesure.');
  });

  it('creates a new topic and shows its empty conversation state', () => {
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

    chatPage.visit();
    topicsPanel.waitForTopicList();

    topicsPanel.createTopic('New thread');

    cy.wait('@createTopic');
    topicsPanel.waitForTopicDetail().waitForTopicList();

    topicsPanel.expectTopicSelected('New thread');
    topicsPanel.expectEmptyState('Commencez la conversation');
  });

  it('lists multiple topics and loads their histories when switching', () => {
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

    chatPage.visit();
    topicsPanel.waitForTopicList();
    topicsPanel.waitForTopicDetail('bugfixDetail');

    topicsPanel.expectTopicExists('Sprint 12').expectTopicExists('Bugfix');
    chatPage.expectAssistantMessageContains('Please try restarting');

    topicsPanel.selectTopic('Sprint 12');
    topicsPanel.waitForTopicDetail('sprintDetail');
    chatPage.expectAssistantMessageContains('Sure thing');
  });

  it('navigates to the Build RAG page and triggers an index build', () => {
    stubTopicList([]);
    stubBuildRag();

    chatPage.visit();
    chatPage.clickBuildRagNav();

    const buildRagPage = new BuildRagPage();
    buildRagPage.assertOnPage();
    buildRagPage.typeRootPath('/workspace/project').launchBuild();

    cy.wait('@buildRag').its('request.body').should('deep.equal', { root: '/workspace/project' });
    buildRagPage.expectToastMessage('RAG index build triggered.');
  });

  it('opens the topic search overlay and switches to a matched topic', () => {
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

    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    cy.clock();
    topicsPanel.openTopicSearch();
    cy.tick(0);
    topicsPanel.typeTopicSearch('Release');
    cy.tick(600);
    cy.wait('@topicSearch');

    topicsPanel.expectTopicSearchResult('Release planning').selectTopicFromSearch('Release planning');
    topicsPanel.waitForTopicDetail('releaseDetail');
    chatPage.expectAssistantMessageContains('Launch readiness confirmed');
  });

  it('shows grouped global search results and loads more entries per category', () => {
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

    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();

    cy.clock();
    globalSearch.typeQuery('doc');
    cy.tick(600);
    cy.wait('@globalSearchInitial');

    globalSearch
      .expectResultInGroup('topics', 'Docs guide')
      .expectResultInGroup('questions', 'How to improve docs?')
      .expectResultInGroup('answers', 'Use OpenAPI for docs')
      .expectMoreButton('topics')
      .expectMoreButton('answers');

    globalSearch.clickMore('topics');
    cy.wait('@globalSearchTopicsMore');
    globalSearch.expectResultInGroup('topics', 'Docs QA').expectMoreButton('topics', false);

    globalSearch.clickMore('answers');
    cy.wait('@globalSearchAnswersMore');
    globalSearch.expectResultInGroup('answers', 'Automate doc deploys').expectMoreButton('answers', false);
  });
});
