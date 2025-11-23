import { BuildRagPage } from '../support/pageObjects/BuildRagPage';
import { ChatPage } from '../support/pageObjects/ChatPage';
import { TopicsPanel } from '../support/pageObjects/TopicsPanel';
import {
  stubBuildRag,
  stubCreateTopic,
  stubSendQuestion,
  stubTopicDetail,
  stubTopicList,
} from '../support/utils/apiStubs';

const chatPage = new ChatPage();
const topicsPanel = new TopicsPanel();

describe('AI Code Assistant app', () => {
  it('sends a chat message and renders assistant reply', () => {
    stubTopicList([{ id: 1, name: 'Sprint 12', message_count: 0 }]);
    stubTopicDetail({ id: 1, name: 'Sprint 12', message_count: 0, messages: [] });
    stubSendQuestion(
      {
        question: 'Bonjour, aide-moi !',
        system_prompt: 'code expert',
        topic_id: '1',
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
        topic_id: '2',
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
    cy.intercept('GET', 'http://localhost:8000/api/topics/', (req) => {
      listCall += 1;
      if (listCall === 1) {
        req.reply({ topics: [] });
        return;
      }

      req.reply({ topics: [{ id: 3, name: 'New thread', message_count: 0 }] });
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
      { id: 1, name: 'Sprint 12', message_count: 2 },
      { id: 2, name: 'Bugfix', message_count: 1 },
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
});
