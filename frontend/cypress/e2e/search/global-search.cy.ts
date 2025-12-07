import { ChatPage } from '../../support/pageObjects/ChatPage';
import { GlobalSearch } from '../../support/pageObjects/GlobalSearch';
import { TopicsPanel } from '../../support/pageObjects/TopicsPanel';
import { stubRagSources, stubSearch, stubTopicDetail, stubTopicList } from '../../support/utils/apiStubs';

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
    stubSearch({
      query: 'documentation',
      filters: {},
      results: {
        answers: [
          { id: '1', title: 'Automate doc deploys', snippet: 'CI/CD pipeline' },
          { id: '2', title: 'Publish docs', snippet: 'Publish flow' },
        ],
        files: [],
      },
    });

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList();
    globalSearch.search('documentation');

    // Assert
    globalSearch.expectResultInGroup('answers', 'Automate doc deploys').expectMoreButton('answers', false);
  });
});
