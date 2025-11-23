export class ChatPage {
  visit() {
    cy.visit('/');
    return this;
  }

  typeQuestion(question: string) {
    cy.get('[data-cy="question-input"]').type(question);
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
