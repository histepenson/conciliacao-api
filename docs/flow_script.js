/**
 * Captura o fluxo completo de conciliação com dados reais.
 * SAO MIGUEL · 31/01/2026
 */
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3000';
const OUT = path.join(__dirname, 'screenshots');
const [,, EMAIL, SENHA] = process.argv;

let page, browser;

async function shot(name, desc) {
  await new Promise(r => setTimeout(r, 800));
  const file = path.join(OUT, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`✓ ${name}.png${desc ? ' — ' + desc : ''}`);
}

async function dismissToasts() {
  await page.evaluate(() => {
    document.querySelectorAll('[data-hot-toast], .hot-toast, [class*="toast"]').forEach(el => el.remove());
  });
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
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('input[type="email"]');
    await page.type('input[type="email"]', EMAIL, { delay: 40 });
    await page.type('input[type="password"]', SENHA, { delay: 40 });
    await shot('01_login', 'tela de login');
    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => {});
    await new Promise(r => setTimeout(r, 2000));
    await dismissToasts();
    await shot('04_dashboard', 'dashboard após login');

    // ── CONCILIAR PERÍODO ──────────────────────────────────────────────
    await page.goto(`${BASE_URL}/conciliacoes/periodo`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await dismissToasts();
    await shot('05_periodo_vazio', 'conciliar período — vazio');

    // Seleciona a empresa SAO MIGUEL
    await page.waitForSelector('select', { timeout: 8000 });
    const empresaSelect = await page.$('select');

    // Loga as opções disponíveis
    const opcoes = await page.evaluate(() => {
      const sel = document.querySelector('select');
      return Array.from(sel.options).map(o => ({ val: o.value, txt: o.text }));
    });
    console.log('Empresas disponíveis:', JSON.stringify(opcoes));

    // Tenta selecionar SAO MIGUEL (case-insensitive)
    const miguel = opcoes.find(o => o.txt.toUpperCase().includes('MIGUEL') || o.txt.toUpperCase().includes('SAO MIGUEL'));
    if (miguel) {
      await page.select('select', miguel.val);
      console.log(`→ Selecionada empresa: ${miguel.txt} (${miguel.val})`);
    } else {
      // Seleciona a primeira empresa disponível que não seja placeholder
      const primeira = opcoes.find(o => o.val && o.val !== '' && o.val !== '0');
      if (primeira) {
        await page.select('select', primeira.val);
        console.log(`→ SAO MIGUEL não encontrada, usando: ${primeira.txt}`);
      }
    }

    await new Promise(r => setTimeout(r, 1000));

    // Preenche a data 31/01/2026
    // Tenta diferentes seletores para o campo de data
    const dateInput = await page.$('input[type="date"], input[placeholder*="DD/MM"], input[placeholder*="data"], input[name*="data"]');
    if (dateInput) {
      await dateInput.click({ clickCount: 3 });
      await dateInput.type('31/01/2026');
      await page.keyboard.press('Tab');
    } else {
      // Tenta pelo placeholder exato
      const inputs = await page.$$('input');
      for (const inp of inputs) {
        const ph = await page.evaluate(el => el.placeholder, inp);
        if (ph && ph.includes('DD/MM')) {
          await inp.click({ clickCount: 3 });
          await inp.type('31/01/2026');
          await page.keyboard.press('Tab');
          break;
        }
      }
    }

    await new Promise(r => setTimeout(r, 1500));
    await dismissToasts();
    await shot('05b_periodo_empresa_data', 'empresa e data preenchidas');

    // Aguarda contas carregarem
    await new Promise(r => setTimeout(r, 2000));
    await dismissToasts();
    await shot('05c_periodo_contas', 'contas disponíveis para conciliar');

    // Clica na primeira conta disponível
    const contaBtn = await page.$('button[data-conta], .conta-item button, .conta-row, tr[data-conta], tbody tr button, .conciliar-btn, button[class*="conta"]');

    // Tenta um clique mais genérico em qualquer botão de conta
    const botoes = await page.$$('button');
    let clicou = false;
    for (const btn of botoes) {
      const txt = await page.evaluate(el => el.textContent.trim().toLowerCase(), btn);
      const tipo = await page.evaluate(el => el.type, btn);
      if (tipo === 'submit') continue;
      if (txt.includes('conciliar') || txt.includes('selecionar') || txt.includes('iniciar') || txt.includes('a receber') || txt.includes('a pagar')) {
        console.log(`→ Clicando botão: "${txt}"`);
        await btn.click();
        clicou = true;
        break;
      }
    }

    if (!clicou) {
      // Tenta clicar em qualquer linha de tabela
      const linhas = await page.$$('tbody tr');
      if (linhas.length > 0) {
        console.log(`→ Clicando na primeira linha da tabela`);
        await linhas[0].click();
        clicou = true;
      }
    }

    await new Promise(r => setTimeout(r, 2000));
    await dismissToasts();
    await shot('05d_periodo_apos_clique', 'após clicar na conta');

    // Verifica se houve modal de tipo de conciliação
    await new Promise(r => setTimeout(r, 1000));
    const modal = await page.$('[role="dialog"], .modal, [class*="modal"], [class*="dialog"]');
    if (modal) {
      await shot('05e_modal_tipo', 'modal de seleção de tipo de conciliação');
      // Clica no primeiro botão do modal (A Receber)
      const modalBtns = await modal.$$('button');
      for (const btn of modalBtns) {
        const txt = await page.evaluate(el => el.textContent.trim(), btn);
        console.log(`Modal botão: "${txt}"`);
      }
      if (modalBtns.length > 0) {
        const btnTexts = await Promise.all(modalBtns.map(b => page.evaluate(el => el.textContent.trim().toLowerCase(), b)));
        const recIdx = btnTexts.findIndex(t => t.includes('receber'));
        const idx = recIdx >= 0 ? recIdx : 0;
        console.log(`→ Clicando: "${btnTexts[idx]}"`);
        await modalBtns[idx].click();
        await new Promise(r => setTimeout(r, 2000));
        await dismissToasts();
        await shot('06_conciliacao_tela', 'tela de conciliação após seleção de tipo');
      }
    } else {
      // Verifica se já navegou para a tela de conciliação
      const url = page.url();
      console.log(`URL atual: ${url}`);
      await shot('06_conciliacao_tela', 'tela de conciliação');
    }

    // ── ACOMPANHAMENTO ────────────────────────────────────────────────
    await page.goto(`${BASE_URL}/acompanhamento-fechamentos`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2500));
    await dismissToasts();
    await shot('10_acompanhamento', 'acompanhamento de fechamentos');

    console.log(`\n✅ Capturas salvas em ${OUT}`);
  } catch (err) {
    console.error('ERRO:', err.message);
    await shot('erro_debug', 'erro');
  } finally {
    await browser.close();
  }
})();
