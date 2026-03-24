const { chromium } = require('playwright');

(async () => {
  const targets = ['https://ops.saillant.cc', 'https://mascarade.saillant.cc'];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const results = [];

  for (const startUrl of targets) {
    const page = await context.newPage();
    try {
      await page.goto(startUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(3000);

      const finalUrl = page.url();
      const title = await page.title();
      const uiElements = await page.evaluate(() => {
        const selectors = [
          'h1', 'h2', 'button', 'a', 'input', 'label', '[role="button"]', '[aria-label]'
        ];
        const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
        const visible = [];

        for (const el of nodes) {
          if (visible.length >= 20) break;
          const style = window.getComputedStyle(el);
          const rect = el.getBoundingClientRect();
          const isVisible = style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
          if (!isVisible) continue;

          const text = (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || '')
            .replace(/\s+/g, ' ')
            .trim();

          const tag = el.tagName.toLowerCase();
          const id = el.id ? `#${el.id}` : '';
          const type = el.getAttribute('type') ? `[type=${el.getAttribute('type')}]` : '';
          const name = el.getAttribute('name') ? `[name=${el.getAttribute('name')}]` : '';
          const role = el.getAttribute('role') ? `[role=${el.getAttribute('role')}]` : '';
          const label = text || 'no-text';
          const desc = `${tag}${id}${type}${name}${role}: ${label}`;
          if (!visible.includes(desc)) visible.push(desc);
        }

        return visible.slice(0, 3);
      });

      results.push({
        startUrl,
        finalUrl,
        title,
        uiElements,
        ssoRedirect: finalUrl.includes('auth.saillant.cc')
      });
    } catch (error) {
      results.push({
        startUrl,
        error: String(error && error.message ? error.message : error)
      });
    } finally {
      await page.close();
    }
  }

  await browser.close();
  console.log(JSON.stringify({ results }, null, 2));
})();
