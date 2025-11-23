// This file is processed automatically before Cypress test files.
// You can add custom commands or global configuration here.

declare global {
  // eslint-disable-next-line @typescript-eslint/no-namespace
  namespace Cypress {
    interface Chainable {
      getBySel(selector: string): Chainable<JQuery<HTMLElement>>;
    }
  }
}

Cypress.Commands.add('getBySel', (selector: string) => {
  return cy.get(`[data-cy="${selector}"]`);
});
export {};
