import { defineConfig } from 'cypress';

export default defineConfig({
  video: false,
  reporter: 'cypress-multi-reporters',
  reporterOptions: {
    reporterEnabled: 'spec, mocha-junit-reporter',
    mochaJunitReporterReporterOptions: {
      mochaFile: 'test-results/cypress/results-[hash].xml',
      toConsole: false,
      attachments: true,
    },
  },
  e2e: {
    baseUrl: 'http://localhost:4200',
    supportFile: 'cypress/support/e2e.ts',
    specPattern: 'cypress/e2e/**/*.cy.{js,ts,jsx,tsx}',
  },
});
