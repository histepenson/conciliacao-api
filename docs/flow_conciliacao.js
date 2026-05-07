/**
 * Captura fluxo completo: SÃO MIGUEL · 31/01/2026
 * Bancária · A Receber · A Pagar
 */
const puppeteer = require('puppeteer');
const path = require('path');

const BASE = 'http://localhost:3000';
const OUT  = path.join(__dirname, 'screenshots');
const [,, EMAIL, SENHA] = process.argv;

let page, browser;

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function shot(name, desc) {
  await sleep(1000);
  await page.screenshot({ path: path.join(OUT, `${name}.png`), fullPage: true });
  console.log(`  ✓ ${name}.png${desc ? '  —  ' + desc : ''}`);
}

async function dismissToasts() {
  await page.evaluate(() => {
    document.querySelectorAll('[data-hot-toast], [class*="toast"], [class*="Toast"]')
      .forEach(el => el.remove());
  }).catch(() => {});
}

async function login() {
  await page.goto(`${BASE}/login`);
  await page.waitForSelector('input[type="email"]');
  await shot('01_login', 'tela de login');
  await page.type('input[type="email"]', EMAIL, { delay: 40 });
  await page.type('input[type="password"]', SENHA, { delay: 40 });
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => {});
  await sleep(2000);
  await dismissToasts();
  await shot('02_dashboard', 'dashboard após login');
}

async function abrirPeriodo() {
  await page.goto(`${BASE}/conciliacoes/periodo`, { waitUntil: 'networkidle2' });
  await sleep(2000);
  await dismissToasts();
}

async function selecionarEmpresaEData() {
  await page.waitForSelector('select', { timeout: 8000 });
  await sleep(2000);

  const opts = await page.evaluate(() =>
    Array.from(document.querySelector('select').options)
      .map(o => ({ v: o.value, t: o.text }))
  );
  console.log('  Empresas:', opts.map(o => o.t).join(' | '));

  const alvo = opts.find(o => o.t.includes('MIGUEL')) || opts.find(o => o.v && o.v !== '');
  if (!alvo) { console.error('  Nenhuma empresa'); return false; }

  await page.select('select', alvo.v);
  console.log(`  → Empresa: ${alvo.t}`);
  await sleep(3000);
  await dismissToasts();

  const numContas = await page.evaluate(() =>
    (document.body.innerText.match(/(\d+)\s*conta/i) || [])[1] || '?'
  );
  console.log(`  Contas encontradas: ${numContas}`);

  // Preencher data 31/01/2026
  await page.evaluate(() => {
    const campo = Array.from(document.querySelectorAll('input')).find(i =>
      i.placeholder?.includes('DD') || i.type === 'date' || i.placeholder?.toLowerCase().includes('data')
    );
    if (!campo) return;
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(campo, '31/01/2026');
    campo.dispatchEvent(new Event('input', { bubbles: true }));
    campo.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(1500);
  await dismissToasts();
  return true;
}

async function clicarContaBotao(textoBusca) {
  /**
   * Encontra a conta pelo texto (usando innerText normalizado) e clica no botão dentro dela.
   */
  const resultado = await page.evaluate((busca) => {
    const contas = Array.from(document.querySelectorAll('.conta-item, [class*="conta-item"]'));
    // Normaliza espaços no innerText para comparação
    const alvo = contas.find(el => {
      const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').toUpperCase();
      return txt.includes(busca.toUpperCase());
    });
    if (!alvo) return null;

    const btn = alvo.querySelector('button');
    if (btn) {
      btn.scrollIntoView({ behavior: 'instant', block: 'center' });
      btn.click();
      return { clicked: btn.textContent.trim(), conta: (alvo.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 100) };
    }
    alvo.scrollIntoView({ behavior: 'instant', block: 'center' });
    alvo.click();
    return { clicked: 'container', conta: (alvo.innerText || '').trim().replace(/\s+/g, ' ').slice(0, 100) };
  }, textoBusca);

  if (resultado) {
    console.log(`  → Conta: "${resultado.conta}"`);
    console.log(`  → Botão: "${resultado.clicked}"`);
    return true;
  }
  console.warn(`  ⚠ Não encontrou conta: "${textoBusca}"`);
  return false;
}

async function clicarBotaoModal(textoBusca) {
  /**
   * Clica em botão dentro do modal que contenha o texto.
   */
  const modal = await page.$('[role="dialog"], .modal-container, [class*="modal"]');
  if (!modal) return false;

  const btns = await modal.$$('button');
  for (const btn of btns) {
    const t = await page.evaluate(el => el.textContent.trim().toUpperCase(), btn);
    if (t.includes(textoBusca.toUpperCase())) {
      await btn.click();
      console.log(`    → Clicado no modal: "${t}"`);
      await sleep(800);
      return true;
    }
  }
  return false;
}

async function tratarModalBancaria() {
  /** Bancária: FINANCEIRO → ATIVO → BANCO */
  await sleep(1200);
  await dismissToasts();
  const modal = await page.$('[role="dialog"], .modal-container, [class*="modal"]');
  if (!modal) { console.log('  (sem modal)'); return; }
  await shot('banco_modal_1', 'modal — escolha tipo');
  await clicarBotaoModal('FINANCEIRO');
  await shot('banco_modal_2', 'modal — ativo ou passivo');
  await clicarBotaoModal('ATIVO');
  await shot('banco_modal_3', 'modal — banco ou contas receber');
  await clicarBotaoModal('BANCO');
}

async function tratarModalReceber() {
  /** A Receber: FINANCEIRO → ATIVO → CONTAS RECEBER */
  await sleep(1200);
  await dismissToasts();
  const modal = await page.$('[role="dialog"], .modal-container, [class*="modal"]');
  if (!modal) { console.log('  (sem modal)'); return; }
  await shot('receber_modal_1', 'modal — escolha tipo');
  await clicarBotaoModal('FINANCEIRO');
  await shot('receber_modal_2', 'modal — ativo ou passivo');
  await clicarBotaoModal('ATIVO');
  await shot('receber_modal_3', 'modal — banco ou contas receber');
  await clicarBotaoModal('CONTAS');
}

async function tratarModalPagar() {
  /** A Pagar: FINANCEIRO → PASSIVO */
  await sleep(1200);
  await dismissToasts();
  const modal = await page.$('[role="dialog"], .modal-container, [class*="modal"]');
  if (!modal) { console.log('  (sem modal)'); return; }
  await shot('pagar_modal_1', 'modal — escolha tipo');
  await clicarBotaoModal('FINANCEIRO');
  await shot('pagar_modal_2', 'modal — ativo ou passivo');
  await clicarBotaoModal('PASSIVO');
}

(async () => {
  browser = await puppeteer.launch({
    headless: true,
    defaultViewport: { width: 1440, height: 900 },
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  page = await browser.newPage();
  page.setDefaultNavigationTimeout(30000);

  try {
    // ── LOGIN ──────────────────────────────────────────────────────────
    console.log('\n── Login ──');
    await login();

    // ══════════════════════════════════════════════════════════════════
    // FLUXO 1 · CONCILIAÇÃO BANCÁRIA
    // ══════════════════════════════════════════════════════════════════
    console.log('\n══ FLUXO 1: BANCÁRIA ══');
    await abrirPeriodo();
    await shot('banco_01_periodo_vazio', 'conciliar período — tela inicial');

    await selecionarEmpresaEData();
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(400);
    await shot('banco_02_empresa_data', 'SÃO MIGUEL · 31/01/2026 · contas carregadas');

    await page.evaluate(() => window.scrollTo(0, 500));
    await sleep(600);
    await shot('banco_02b_contas_bancos', 'contas bancárias disponíveis');

    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(300);
    await clicarContaBotao('27985');
    await tratarModalBancaria();

    await sleep(2500);
    await dismissToasts();
    console.log('  URL:', page.url());
    await shot('banco_03_tela', 'tela de conciliação bancária');
    await page.evaluate(() => window.scrollTo(0, 400));
    await sleep(500);
    await shot('banco_04_campos', 'bancária — campos de parâmetros');

    // ══════════════════════════════════════════════════════════════════
    // FLUXO 2 · CONTAS A RECEBER
    // ══════════════════════════════════════════════════════════════════
    console.log('\n══ FLUXO 2: A RECEBER ══');
    await abrirPeriodo();
    await selecionarEmpresaEData();

    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(400);
    await shot('receber_01_periodo', 'período com SÃO MIGUEL selecionado');

    await clicarContaBotao('DISTRIBUIDORA ARAGUAIA');
    await tratarModalReceber();

    await sleep(2500);
    await dismissToasts();
    console.log('  URL:', page.url());
    await shot('receber_02_tela', 'tela de conciliação A Receber');
    await page.evaluate(() => window.scrollTo(0, 400));
    await sleep(500);
    await shot('receber_03_campos', 'A Receber — campos de parâmetros');

    // ══════════════════════════════════════════════════════════════════
    // FLUXO 3 · CONTAS A PAGAR
    // ══════════════════════════════════════════════════════════════════
    console.log('\n══ FLUXO 3: A PAGAR ══');
    await abrirPeriodo();
    await selecionarEmpresaEData();

    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(400);
    await shot('pagar_01_periodo', 'período — visão geral das contas');

    await clicarContaBotao('NIDERA');
    await tratarModalPagar();

    await sleep(2500);
    await dismissToasts();
    console.log('  URL:', page.url());
    await shot('pagar_02_tela', 'tela de conciliação A Pagar');
    await page.evaluate(() => window.scrollTo(0, 400));
    await sleep(500);
    await shot('pagar_03_campos', 'A Pagar — campos de parâmetros');

    // ── ACOMPANHAMENTO ────────────────────────────────────────────────
    console.log('\n── Acompanhamento ──');
    await page.goto(`${BASE}/acompanhamento-fechamentos`, { waitUntil: 'networkidle2' });
    await sleep(2500);
    await dismissToasts();
    await shot('10_acompanhamento', 'acompanhamento de fechamentos');

    console.log('\n✅ Concluído em', OUT);

  } catch (err) {
    console.error('\n❌ ERRO:', err.message);
    await shot('erro_debug', 'estado no erro').catch(() => {});
  } finally {
    await browser.close();
  }
})();
