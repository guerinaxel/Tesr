export class ChatPage {
  visit() {
    cy.visit('/');
    return this;
  }

  typeQuestion(question: string) {
    cy.get('[data-cy="question-input"]').type(question);
    return this;
  }

  typeQuestionWithEnter(question: string) {
    cy.get('[data-cy="question-input"]').type(`${question}{enter}`);
    return this;
  }

  clickSend() {
    cy.get('[data-cy="send-button"]').click();
    return this;
  }

  expectSendDisabled() {
    cy.get('[data-cy="send-button"]').should('be.disabled');
    return this;
  }

  expectSendEnabled() {
    cy.get('[data-cy="send-button"]').should('not.be.disabled');
    return this;
  }

  selectSystemPrompt(option: string) {
    cy.get('[data-cy="system-prompt-select"]').click();
    cy.get('mat-option').contains(option).click();
    return this;
  }

  selectRagSources(names: string[]) {
    cy.get('[data-cy="rag-source-select"]').click();
    names.forEach((name) => {
      cy.get('mat-option').contains(name).click();
    });
    cy.get('body').click('topRight');
    return this;
  }

  editRagSource(originalName: string, newName: string, newDescription: string) {
    cy.contains('[data-cy="rag-source-card"]', originalName)
      .find('[data-cy="edit-rag-source"]')
      .click();
    cy.get('[data-cy="edit-rag-name"]').clear().type(newName);
    cy.get('[data-cy="edit-rag-description"]').clear().type(newDescription);
    cy.get('[data-cy="submit-edit-rag"]').click();
    return this;
  }

  rebuildRagSource(name: string, paths: string) {
    cy.contains('[data-cy="rag-source-card"]', name)
      .find('[data-cy="rebuild-rag-source"]')
      .click();
    cy.get('[data-cy="rebuild-rag-paths"]').type(paths);
    cy.get('[data-cy="submit-rebuild-rag"]').click();
    return this;
  }

  typeCustomPrompt(prompt: string) {
    cy.get('[data-cy="custom-prompt-input"]').should('be.visible').type(prompt);
    return this;
  }

  expectUserMessageContains(text: string) {
    cy.get('.message--user .message__content').should('contain', text);
    return this;
  }

  expectAssistantMessageContains(text: string) {
    cy.get('.message--assistant .message__content').should('contain', text);
    return this;
  }

  expectAssistantMessageCount(count: number) {
    cy.get('[data-cy="messages"]').find('.message--assistant').should('have.length', count);
    return this;
  }

  clickBuildRagNav() {
    cy.get('[data-cy="build-rag-nav"]', { timeout: 10000 }).click();
    return this;
  }
}
