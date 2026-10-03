import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';
const browser=await puppeteer.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-webgl','--ignore-gpu-blocklist','--enable-unsafe-swiftshader','--use-gl=angle','--use-angle=swiftshader','--disable-vulkan'],protocolTimeout:120000});
try {
 const page=await browser.newPage();await page.setViewport({width:1440,height:1050});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:8765',{waitUntil:'domcontentloaded'});
 const token=(await fs.readFile('/home/digi070/.local/share/digi/access-token','utf8')).trim();
 await page.evaluate(async token=>{const r=await fetch('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token})});if(!r.ok)throw Error('Auth failed');},token);
 await page.reload({waitUntil:'domcontentloaded'});errors.length=0;
 await page.click('[data-view="godsEye"]');
 await page.type('#gev-place','Paris, France');await page.click('#gev-place-form button');
 await page.waitForFunction(()=>document.querySelector('#gev-details').textContent.includes('48.853'),{timeout:90000});
 await page.waitForFunction(()=>document.querySelector('#gev-status').textContent==='Globe updated.',{timeout:60000});
 const frame=page.frames().find(f=>f.url().includes('4173'));
 const state=await frame.evaluate(()=>({viewer:!!window.__godsEyeView?.viewer,embedded:document.body.classList.contains('ui-embed'),canvas:!!document.querySelector('canvas')}));
 await new Promise(r=>setTimeout(r,12000));
 console.log('camera',await frame.evaluate(()=>{const v=window.__godsEyeView.viewer,p=v.camera.positionCartographic;return {lat:p.latitude*180/Math.PI,lon:p.longitude*180/Math.PI,height:p.height,tilesLoaded:v.scene.globe.tilesLoaded};}));
 await page.screenshot({path:'/home/digi070/Work/digi/docs/verification/gods-eye/paris-sidebar.png'});
 await page.click('#gev-controls');
 await page.waitForFunction(()=>document.querySelector('#gev-status').textContent==='Globe updated.',{timeout:90000});
 await page.waitForFunction(async()=>{const r=await fetch('/api/gods-eye');const o=(await r.json()).observed_view;return o&&Math.abs(o.camera.lat-48.8535)<.01;},{timeout:30000});
 const observed=await page.evaluate(async()=>{const r=await fetch('/api/gods-eye');return (await r.json()).observed_view;});
 const controls=await page.frames().find(f=>f.url().includes('4173')).evaluate(()=>({embedded:document.body.classList.contains('ui-embed'),viewer:!!window.__godsEyeView?.viewer}));
 console.log(JSON.stringify({state,controls,observed,errors},null,2));
 if(!state.viewer||!state.canvas||!controls.viewer||controls.embedded||!observed||errors.length)process.exitCode=1;
} finally {await browser.close();}
