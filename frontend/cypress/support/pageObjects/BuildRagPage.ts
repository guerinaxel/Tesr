export class BuildRagPage {
  assertOnPage() {
    cy.url().should('include', '/build-rag');
    return this;
  }

  expectRootValue(path: string) {
    cy.get('[data-cy="root-input"]').should('have.value', path);
    return this;
  }

  typeRootPath(path: string) {
    cy.get('[data-cy="root-input"]').clear().type(path);
    return this;
  }

  launchBuild() {
    cy.get('[data-cy="launch-button"]').click();
    return this;
  }

  clickRebuild() {
    cy.get('[data-cy="rebuild-button"]').click();
    return this;
  }

  expectToastMessage(text: string) {
    cy.get('[data-cy="toast"]').should('be.visible').and('contain', text);
    return this;
  }

  expectProgress(message: string, percent: number) {
    cy.get('[data-cy="build-progress"]').should('be.visible');
    cy.get('[data-cy="progress-message"]').should('contain', message);
    cy.get('[data-cy="progress-percent"]').should('contain', `${percent}%`);
    return this;
  }
}
