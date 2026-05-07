/**
 * Script de captura de screenshots para documentação do usuário.
 * Uso: node screenshot_script.js <email> <senha>
 */

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const BASE_URL = 'http://localhost:3000';
const OUT_DIR = path.join(__dirname, 'screenshots');

const [,, EMAIL, SENHA] = process.argv;
if (!EMAIL || !SENHA) {
  console.error('Uso: node screenshot_script.js <email> <senha>');
  process.exit(1);
}

if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

async function shot(page, name, { fullPage = true } = {}) {
  const file = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: file, fullPage });
  console.log(`✓ ${name}.png`);
  return file;
}

async function waitAndShot(page, selector, name) {
  await page.waitForSelector(selector, { timeout: 10000 }).catch(() => {});
  await shot(page, name);
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
    // ── 1. Tela de Login ──────────────────────────────────────────────
    console.log('\n── Login ──');
    await page.goto(`${BASE_URL}/login`);
    await page.waitForSelector('input[type="email"], input[name="email"]', { timeout: 10000 });
    await shot(page, '01_login');

    // Preenche credenciais
    await page.type('input[type="email"], input[name="email"]', EMAIL, { delay: 30 });
    await page.type('input[type="password"], input[name="password"]', SENHA, { delay: 30 });
    await shot(page, '02_login_preenchido');
    await page.keyboard.press('Enter');
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 1500));

    // Pode redirecionar para select-empresa
    if (page.url().includes('select-empresa')) {
      await shot(page, '03_selecionar_empresa');
      // Clica na primeira empresa disponível
      const btn = await page.$('button, .empresa-item, [data-empresa], li');
      if (btn) { await btn.click(); await page.waitForNavigation({ waitUntil: 'networkidle2' }).catch(() => {}); }
      await new Promise(r => setTimeout(r, 1000));
    }

    // ── 2. Dashboard ──────────────────────────────────────────────────
    console.log('\n── Dashboard ──');
    await page.goto(`${BASE_URL}/`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '04_dashboard');

    // ── 3. Selecionar Período ─────────────────────────────────────────
    console.log('\n── Selecionar Período ──');
    await page.goto(`${BASE_URL}/conciliacoes/periodo`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '05_conciliacao_selecionar_periodo');

    // ── 4. Conciliação (A Receber) ────────────────────────────────────
    console.log('\n── Conciliação ──');
    await page.goto(`${BASE_URL}/conciliacoes`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '06_conciliacao_upload');

    // ── 5. Conciliação A Pagar ────────────────────────────────────────
    await page.goto(`${BASE_URL}/conciliacoes/pagar`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '07_conciliacao_pagar');

    // ── 6. Conciliação Bancária ───────────────────────────────────────
    await page.goto(`${BASE_URL}/conciliacoes/banco`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '08_conciliacao_banco');

    // ── 7. Conciliação Estoque ────────────────────────────────────────
    await page.goto(`${BASE_URL}/conciliacoes/estoque`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '09_conciliacao_estoque');

    // ── 8. Acompanhamento de Fechamentos ──────────────────────────────
    console.log('\n── Acompanhamento ──');
    await page.goto(`${BASE_URL}/acompanhamento-fechamentos`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '10_acompanhamento_fechamentos');

    // ── 9. Cadastros – Empresas ───────────────────────────────────────
    console.log('\n── Cadastros ──');
    await page.goto(`${BASE_URL}/cadastros/empresas`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '11_cadastros_empresas');

    // ── 10. Cadastros – Plano de Contas ───────────────────────────────
    await page.goto(`${BASE_URL}/cadastros/planocontas`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '12_cadastros_planocontas');

    // ── 11. Estoque – Produtos ────────────────────────────────────────
    console.log('\n── Estoque ──');
    await page.goto(`${BASE_URL}/estoque/produtos`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '13_estoque_produtos');

    // ── 12. Estoque – De-Para ─────────────────────────────────────────
    await page.goto(`${BASE_URL}/estoque/de-para`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '14_estoque_depara');

    // ── 13. Estoque – NF-e ────────────────────────────────────────────
    await page.goto(`${BASE_URL}/estoque/nfe`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '15_estoque_nfe');

    // ── 14. Estoque – Saldos ──────────────────────────────────────────
    await page.goto(`${BASE_URL}/estoque/saldo`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '16_estoque_saldo');

    // ── 15. Estoque – Movimentações ───────────────────────────────────
    await page.goto(`${BASE_URL}/estoque/movimentacoes`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '17_estoque_movimentacoes');

    // ── 16. Estoque – Fechamento ──────────────────────────────────────
    await page.goto(`${BASE_URL}/estoque/fechamento`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '18_estoque_fechamento');

    // ── 17. Admin – Usuários ──────────────────────────────────────────
    console.log('\n── Admin ──');
    await page.goto(`${BASE_URL}/admin/usuarios`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '19_admin_usuarios');

    // ── 18. Admin – Perfis ────────────────────────────────────────────
    await page.goto(`${BASE_URL}/admin/perfis`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 1500));
    await shot(page, '20_admin_perfis');

    // ── 19. Esqueci a Senha ───────────────────────────────────────────
    console.log('\n── Auth extra ──');
    await page.goto(`${BASE_URL}/forgot-password`, { waitUntil: 'networkidle2' });
    await new Promise(r => setTimeout(r, 800));
    await shot(page, '21_esqueci_senha');

    console.log(`\n✅ Todas as capturas salvas em: ${OUT_DIR}`);
  } catch (err) {
    console.error('Erro durante captura:', err.message);
    await shot(page, 'erro_debug');
  } finally {
    await browser.close();
  }
})();
