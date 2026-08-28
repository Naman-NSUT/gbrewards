import { chromium } from '/home/nonu/gbrewards/admin-web/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const TOKEN = fs.readFileSync('/home/nonu/gbrewards/.seed-admin-token','utf8').trim();
const API = 'http://127.0.0.1:8010/api/v1';
const H = { Authorization: `Bearer ${TOKEN}` };

const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
page.on('console', m => { if (m.type()==='error' && !/ERR_NETWORK_CHANGED/.test(m.text())) errors.push('CONSOLE: '+m.text().slice(0,160)); });
await page.addInitScript(t => {
  localStorage.setItem('dr_admin_access', t);
  localStorage.setItem('dr_admin_refresh', t);
  localStorage.setItem('dr_admin_profile', JSON.stringify({id:'x',email:'dealer@local.test',name:'Ops',role:'owner'}));
}, TOKEN);

await page.goto('http://localhost:4402/dealer/products', { waitUntil:'networkidle' });
await page.waitForTimeout(1500);

const body = await page.locator('body').innerText();
console.log('=== points column ===');
console.log(`  shows "120 / sale"   : ${/120\s*\/ sale/.test(body)}`);
console.log(`  shows "60 / sale"    : ${/\b60\s*\/ sale/.test(body)}`);
console.log(`  flags the unpriced   : ${body.includes('not set')}`);

console.log('=== add a product WITH points, through the form ===');
await page.getByRole('button', { name: /Add product/i }).click();
await page.waitForTimeout(600);
const NAME = 'Test Pocket Spring ' + Date.now().toString().slice(-5);
await page.locator('.ant-modal input#name').fill(NAME);
await page.locator('.ant-modal input#points_per_registration').fill('245');
await page.getByRole('button', { name: /^Save$/ }).last().click();
await page.waitForTimeout(2000);

const after = await page.locator('body').innerText();
console.log(`  row rendered with 245 : ${after.includes(NAME) && /245\s*\/ sale/.test(after)}`);

// the rate must actually exist server-side, not just in the table
const rates = await (await fetch(`${API}/dealer-admin/points/rates/current`, { headers: H })).json();
const made = rates.find(r => r.product_name === NAME);
console.log(`  server rate persisted : ${made ? made.points_per_registration : 'NO ROW'}`);

await page.screenshot({ path:'/home/nonu/gbrewards/.products.png', fullPage:true });
await browser.close();
console.log(errors.length ? '  ERRORS: '+errors.join(' | ') : '  no console errors');
