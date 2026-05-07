/**
 * Retira screenshots das páginas de conciliação com fluxo correto.
 */
const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3000';
const OUT_DIR = path.join(__dirname, 'screenshots');
const [,, EMAIL, SENHA] = process.argv;

async function shot(page, name) {
  // Aguarda toasts sumirem (3s)
  await new Promise(r => setTimeout(r, 3000));
  // Fecha qualquer toast clicando fora
  await page.mouse.click(700, 700).catch(() => {});
  await new Promise(r => setTimeout(r, 500));
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  console.log(`✓ ${name}.png`);
}

(async () => {
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: { width: 1440, height: 900 },
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });
  const page = await browser.newPage();
  page.setDefaultNavigationTimeout(30000);

  try {
    // Login
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('input[type="email"]');
    await page.type('input[type="email"]', EMAIL, { delay: 30 });
    await page.type('input[type="password"]', SENHA, { delay: 30 });
    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => {});
    await new Promise(r => setTimeout(r, 2000));

    // ── Dashboard limpo (aguarda toast sumir) ──
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle2' });
    await shot(page, '04_dashboard');

    // ── Selecionar Período ──
    await page.goto(`${BASE_URL}/conciliacoes/periodo`, { waitUntil: 'networkidle2' });
    await page.waitForSelector('select, input', { timeout: 8000 }).catch(() => {});
    await shot(page, '05_conciliacao_selecionar_periodo');

    // ── Conciliação A Receber ──
    // Navega para a página e injeta o contexto mínimo via localStorage
    await page.goto(`${BASE_URL}/conciliacoes`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    await shot(page, '06_conciliacao_receber');

    // ── Conciliação A Pagar ──
    await page.goto(`${BASE_URL}/conciliacoes/pagar`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    await shot(page, '07_conciliacao_pagar');

    // ── Conciliação Bancária ──
    await page.goto(`${BASE_URL}/conciliacoes/banco`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    await shot(page, '08_conciliacao_banco');

    // ── Conciliação Estoque ──
    await page.goto(`${BASE_URL}/conciliacoes/estoque`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    await shot(page, '09_conciliacao_estoque');

    // ── Acompanhamento ──
    await page.goto(`${BASE_URL}/acompanhamento-fechamentos`, { waitUntil: 'networkidle2' });
    await shot(page, '10_acompanhamento_fechamentos');

    // ── Cadastros ──
    await page.goto(`${BASE_URL}/cadastros/empresas`, { waitUntil: 'networkidle2' });
    await shot(page, '11_cadastros_empresas');

    await page.goto(`${BASE_URL}/cadastros/planocontas`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 2000));
    await shot(page, '12_cadastros_planocontas');

    // ── Estoque ──
    await page.goto(`${BASE_URL}/estoque/produtos`, { waitUntil: 'networkidle2' });
    await shot(page, '13_estoque_produtos');

    await page.goto(`${BASE_URL}/estoque/de-para`, { waitUntil: 'networkidle2' });
    await shot(page, '14_estoque_depara');

    await page.goto(`${BASE_URL}/estoque/nfe`, { waitUntil: 'networkidle2' });
    await shot(page, '15_estoque_nfe');

    await page.goto(`${BASE_URL}/estoque/saldo`, { waitUntil: 'networkidle2' });
    await shot(page, '16_estoque_saldo');

    await page.goto(`${BASE_URL}/estoque/movimentacoes`, { waitUntil: 'networkidle2' });
    await shot(page, '17_estoque_movimentacoes');

    await page.goto(`${BASE_URL}/estoque/fechamento`, { waitUntil: 'networkidle2' });
    await shot(page, '18_estoque_fechamento');

    // ── Admin ──
    await page.goto(`${BASE_URL}/admin/usuarios`, { waitUntil: 'networkidle2' });
    await shot(page, '19_admin_usuarios');

    await page.goto(`${BASE_URL}/admin/perfis`, { waitUntil: 'networkidle2' });
    await shot(page, '20_admin_perfis');

    console.log(`\n✅ Capturas limpas salvas em: ${OUT_DIR}`);
  } catch (err) {
    console.error('Erro:', err.message);
  } finally {
    await browser.close();
  }
})();
