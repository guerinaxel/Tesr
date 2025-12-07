import { ChatPage } from '../../support/pageObjects/ChatPage';
import { TopicsPanel } from '../../support/pageObjects/TopicsPanel';
import {
  stubBuildRag,
  stubRagSources,
  stubRebuildRagSource,
  stubTopicDetail,
  stubTopicList,
  stubUpdateRagSource,
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

describe('RAG sources management', () => {
  it('builds a new RAG source from the UI', () => {
    // Arrange
    stubRagSources(defaultSources);
    stubBuildRag({
      id: 'source-3',
      name: 'Docs',
      description: 'Docs portal',
      path: '/tmp/docs',
      created_at: new Date().toISOString(),
      total_files: 5,
      total_chunks: 7,
    });
    stubTopicList([{ id: 6, name: 'Build RAG', message_count: 0 }]);
    stubTopicDetail({ id: 6, name: 'Build RAG', message_count: 0, messages: [] });

    // Act
    chatPage.visit();
    topicsPanel.waitForTopicList().waitForTopicDetail();
    chatPage.openBuildForm();
    chatPage.fillBuildForm('Docs', 'Docs portal', '/tmp/docs');
    chatPage.submitBuildForm();

    // Assert
    cy.wait('@buildRag').its('request.body').should('deep.equal', {
      name: 'Docs',
      description: 'Docs portal',
      paths: ['/tmp/docs'],
    });
    cy.contains('[data-cy="rag-source-card"]', 'Docs').should('contain', '7');
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
