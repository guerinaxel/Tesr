import { ChatPage } from '../../support/pageObjects/ChatPage';
import { GlobalSearch } from '../../support/pageObjects/GlobalSearch';
import { TopicsPanel } from '../../support/pageObjects/TopicsPanel';
import { of } from 'rxjs';
import { stubRagSources, stubTopicDetail, stubTopicList } from '../../support/utils/apiStubs';

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
];

describe('Search / global search', () => {
  it('performs a global search and navigates to answers tab', () => {
    // Arrange
    stubRagSources(defaultSources);
    stubTopicList([{ id: 5, name: 'Navigation', message_count: 0 }]);
    stubTopicDetail({ id: 5, name: 'Navigation', message_count: 0, messages: [] });
    const searchResponse = {
      topics: { items: [], next_offset: null },
      questions: { items: [], next_offset: null },
      answers: {
        items: [
          { id: 1, topic_id: 5, topic_name: 'Navigation', content: 'Automate doc deploys' },
          { id: 2, topic_id: 5, topic_name: 'Navigation', content: 'Publish docs' },
        ],
        next_offset: null,
      },
    };

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList();
    cy.window()
      .its('appComponent')
      .should('exist')
      .then((app: any) => {
        cy.stub(app['chatDataService'], 'searchEverything').returns(of(searchResponse));
        app.onGlobalSearchChange('documentation');
        app.globalSearchResults.set(searchResponse);
        app.searchVisible.set(true);
      });
    cy.wait(600);

    // Assert
    cy.get('[data-cy="global-search-panel"]').should('exist');
    globalSearch.expectResultInGroup('answers', 'Automate doc deploys').expectMoreButton('answers', false);
  });
});
