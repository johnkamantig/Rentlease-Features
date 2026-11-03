import { defineConfig } from '@playwright/test';

const port = Number(process.env.PORT || 4173);
export default defineConfig({
  testDir: './tests', testMatch: '*.spec.mjs', workers: 1,
  timeout: 60000, expect: { timeout: 15000 },
  use: { baseURL: `http://127.0.0.1:${port}`, viewport: { width: 1100, height: 760 },
    channel: process.env.PLAYWRIGHT_CHANNEL || 'chrome',
    launchOptions: { args: ['--enable-webgl', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: 'node serve.mjs', url: `http://127.0.0.1:${port}`, reuseExistingServer: false, timeout: 15000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
});
