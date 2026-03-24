const { chromium } = require('playwright');
const os = require('os');
const path = require('path');

const userDataDir = path.join(os.homedir(), 'Library', 'Application Support', 'Google', 'Chrome');
const targets = [
  'https://ops.saillant.cc',
  'https://mascarade.saillant.cc',
];

(async () => {
  let context;
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      channel: 'chrome',
      headless: true,
      ignoreHTTPSErrors: true,
    });
  } catch (error) {
    console.error('LAUNCH_ERROR');
    console.error(String((error && error.message) || error));
    process.exit(2);
  }

  const page = context.pages()[0] || await context.newPage();

  for (const url of targets) {
    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      const title = await page.title();
      const finalUrl = page.url();
      const bodyText = await page.locator('body').innerText().catch(() => '');
      const markers = [];

      for (const marker of ['authentik', 'login', 'dashboard', 'cockpit', 'logout', 'projects', 'agents']) {
        if (bodyText.toLowerCase().includes(marker)) {
          markers.push(marker);
        }
      }

      console.log('URL', url);
      console.log('FINAL', finalUrl);
      console.log('TITLE', title);
      console.log('MARKERS', markers.join(', '));
      console.log('---');
    } catch (error) {
      console.log('URL', url);
      console.log('ERROR', String((error && error.message) || error));
      console.log('---');
    }
  }

  await context.close();
})();
