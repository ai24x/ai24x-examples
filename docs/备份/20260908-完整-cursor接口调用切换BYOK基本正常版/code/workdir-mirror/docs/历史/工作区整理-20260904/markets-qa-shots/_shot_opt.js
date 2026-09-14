// QA 截图：优化后桌面/手机（EN/ZH）与 WETOUR 建议提示
const { chromium } = require('playwright-core');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  });
  const out = path.join(__dirname, '..', 'docs');

  async function closeOnboard(page) {
    try {
      if (await page.isVisible('#onboard')) await page.click('#onboard-skip');
    } catch (e) {}
  }

  // Desktop EN
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1800);
    await page.screenshot({ path: path.join(out, 'shot_opt_desktop_en.png') });
    await page.close();
  }

  // Desktop ZH
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1500);
    await page.click('#lang-switch button[data-lang="zh"]');
    await page.waitForTimeout(1600);
    await page.screenshot({ path: path.join(out, 'shot_opt_desktop_zh.png') });
    await page.close();
  }

  // Desktop WETOUR suggestion
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1200);
    await page.fill('#symbol', 'WETOUR');
    await page.click('#go');
    await page.waitForFunction(() => /Did you mean/.test((document.getElementById('err') || {}).textContent || ''), { timeout: 25000 });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(out, 'shot_opt_wetour.png') });
    await page.close();
  }

  // Mobile ZH
  {
    const page = await browser.newPage({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });
    await page.goto('http://127.0.0.1:18012/app.html?symbol=AAPL', { waitUntil: 'networkidle' });
    await closeOnboard(page);
    await page.waitForTimeout(1500);
    await page.click('#lang-switch button[data-lang="zh"]');
    await page.waitForTimeout(1600);
    await page.screenshot({ path: path.join(out, 'shot_opt_mobile_zh.png') });
    await page.close();
  }

  await browser.close();
  console.log('shots saved to ' + out);
})();
