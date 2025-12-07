// Karma configuration file, see link for more information
// https://karma-runner.github.io/6.4/config/configuration-file.html

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

const isCI = !!process.env.CI;
const chromeFlags = [
  '--no-sandbox',
  '--disable-setuid-sandbox',
  '--disable-gpu',
  '--disable-dev-shm-usage',
  '--remote-debugging-port=9222',
];

if (!process.env.CHROME_BIN) {
  process.env.CHROME_BIN = puppeteer.executablePath();
}

module.exports = function (config) {
  const junitOutputDir = path.resolve(
    __dirname,
    process.env.TEST_OUTPUT_DIR || 'test-results'
  );

  if (!fs.existsSync(junitOutputDir)) {
    fs.mkdirSync(junitOutputDir, { recursive: true });
  }

  config.set({
    basePath: '',
    frameworks: ['jasmine', '@angular-devkit/build-angular'],
    plugins: [
      require('karma-jasmine'),
      require('karma-chrome-launcher'),
      require('karma-jasmine-html-reporter'),
      require('karma-coverage'),
      require('karma-junit-reporter'),
      require('@angular-devkit/build-angular/plugins/karma'),
    ],
    client: {
      jasmine: {},
      clearContext: false,
    },
    coverageReporter: {
      dir: require('path').join(__dirname, './coverage/ai-code-assistant-frontend'),
      subdir: '.',
      reporters: [
        { type: 'text-summary' },
        // lcovonly keeps CI fast and avoids heavy HTML generation that can trigger browser ping timeouts
        { type: 'lcovonly' },
      ],
      check: {
        global: {
          statements: 80,
          branches: 80,
          functions: 80,
          lines: 80,
        },
      },
    },
    junitReporter: {
      outputDir: junitOutputDir,
      outputFile: 'karma-results.xml',
      useBrowserName: false,
    },
    reporters: ['progress', 'kjhtml', 'junit'],
    browserNoActivityTimeout: 300000,
    browserDisconnectTimeout: 120000,
    browserSocketTimeout: 300000,
    browserDisconnectTolerance: 5,
    customLaunchers: {
      ChromeHeadlessCI: {
        base: 'ChromeHeadless',
        flags: chromeFlags,
      },
    },
    port: 9876,
    colors: true,
    logLevel: config.LOG_INFO,
    autoWatch: !isCI,
    browsers: [isCI ? 'ChromeHeadlessCI' : 'ChromeHeadlessCI'],
    singleRun: isCI,
    restartOnFileChange: true,
  });
};
