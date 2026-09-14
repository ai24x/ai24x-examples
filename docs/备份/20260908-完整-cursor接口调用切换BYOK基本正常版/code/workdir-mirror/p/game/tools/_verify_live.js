const { chromium } = require('E:/AI24X/_tmp/pwtest/node_modules/playwright-core');
(async()=>{
  const browser = await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
  const page = await browser.newPage({viewport:{width:390,height:844}});
  const files = ['index.html','screw-hero.html','weird-merge.html','arrow-maze.html','neon-snake.html'];
  for (const f of files) {
    const errors=[];
    page.removeAllListeners('pageerror'); page.removeAllListeners('console');
    page.on('pageerror', e=>errors.push('PAGEERROR: '+e.message));
    page.on('console', m=>{if(m.type()==='error'&&!m.text().includes('favicon')) errors.push('CONSOLE: '+m.text());});
    try {
      const resp = await page.goto('https://game.ai24x.com/'+f,{waitUntil:'load',timeout:20000});
      await page.waitForTimeout(900);
      console.log((resp&&resp.status()===200?'200':'HTTP'+(resp&&resp.status()))+' '+f+(errors.length?(' | '+errors.join(' | ')):''));
    } catch(e) { console.log('FAIL '+f+' | '+e.message.split('\n')[0]); }
  }
  await browser.close();
})();
