# 🚀 Sistema de Conciliação com IA - React + Python

Sistema completo de upload e processamento de arquivos de conciliação usando React (frontend) e Python FastAPI (backend).

## 📁 Estrutura do Projeto

```
conciliacao-app/
├── src/                    # Frontend React
│   ├── App.jsx            # Componente principal com lógica
│   ├── main.jsx           # Entry point
│   └── index.css          # Estilos
├── backend/               # Backend Python
│   ├── main.py           # API FastAPI
│   └── requirements.txt  # Dependências Python
├── package.json          # Dependências Node
├── vite.config.js       # Config Vite
└── index.html           # HTML principal
```

## 🎯 Features

### Frontend React
- ✅ Upload de 3 arquivos com drag & drop
- ✅ Validação de formato (.xlsx, .xls, .csv)
- ✅ Validação de tamanho (máx 50MB)
- ✅ Preview de arquivos
- ✅ Indicadores visuais de status
- ✅ Loading state durante processamento
- ✅ Exibição de resultados
- ✅ Tratamento de erros
- ✅ Design responsivo

### Backend Python
- ✅ API REST com FastAPI
- ✅ Recebimento de múltiplos arquivos
- ✅ Leitura de Excel/CSV com Pandas
- ✅ Detecção de duplicatas
- ✅ Matching entre bases
- ✅ Cálculo de diferenças
- ⏳ Integração com Claude IA (TODO)

---

## 🚀 Instalação e Uso

### 1. Frontend React

```bash
# Instalar dependências
npm install

# Iniciar servidor de desenvolvimento
npm run dev
```

O frontend estará disponível em: **http://localhost:3000**

### 2. Backend Python

```bash
# Criar ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows

# Instalar dependências
cd backend
pip install -r requirements.txt

# Iniciar servidor
python main.py
```

A API estará disponível em: **http://localhost:8000**

Documentação automática: **http://localhost:8000/docs**

---

## 📤 Como Usar

### Passo 1: Iniciar Backend
```bash
cd backend
python main.py
```

### Passo 2: Iniciar Frontend
```bash
# Em outro terminal
npm run dev
```

### Passo 3: Usar a Aplicação
1. Abra http://localhost:3000
2. Arraste ou selecione os 3 arquivos:
   - Arquivo Origem (financeiro.xlsx)
   - Arquivo Contábil (fcontabilidade.xlsx)
   - Base Geral Contabilidade (base_geral.xlsx)
3. Clique em "Processar com IA"
4. Aguarde o resultado

---

## 🔌 API Endpoints

### POST /api/conciliacao/processar

Processa os 3 arquivos de conciliação.

**Parâmetros (FormData):**
- `arquivo_origem` (file) - Arquivo financeiro
- `arquivo_contabil` (file) - Arquivo contábil
- `arquivo_geral_contabilidade` (file) - Base geral

**Resposta:**
```json
{
  "success": true,
  "timestamp": "2025-12-03T...",
  "arquivos": {
    "origem": { "nome": "...", "registros": 100 },
    "contabil": { "nome": "...", "registros": 50 },
    "geral": { "nome": "...", "registros": 9208 }
  },
  "analise": {
    "duplicatas_encontradas": 832,
    "matches_realizados": 19,
    "diferencas_identificadas": 6,
    "total_divergencia": -62109297.91
  },
  "detalhes": {
    "duplicatas": [...],
    "diferencas": [...]
  },
  "recomendacoes": [...]
}
```

---

## 🎨 Configuração da API

No arquivo `src/App.jsx`, linha 6:

```javascript
const api = axios.create({
  baseURL: 'http://localhost:8000/api', // Ajuste aqui!
  headers: {
    'Content-Type': 'multipart/form-data',
  },
})
```

Se sua API estiver em outra URL/porta, mude o `baseURL`.

---

## 🔧 Desenvolvimento

### Adicionar nova validação no frontend:

```javascript
// Em App.jsx, função handleFileSelect
const handleFileSelect = (type, file) => {
  // Adicione suas validações aqui
  if (file.size > 100 * 1024 * 1024) {
    alert('Arquivo muito grande!')
    return
  }
  
  // ...resto do código
}
```

### Adicionar novo processamento no backend:

```python
# Em backend/main.py
@app.post("/api/conciliacao/processar")
async def processar_conciliacao(...):
    # Adicione sua lógica aqui
    
    # Exemplo: Chamar Claude IA
    from anthropic import Anthropic
    
    client = Anthropic(api_key="sua-chave")
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Analise estas diferenças: {diferencas}"
        }]
    )
    
    return resultado
```

---

## 📊 Estrutura dos Dados

### Arquivo Origem (financeiro.xlsx)
Colunas esperadas:
- Cliente
- Valor
- Data
- NF (opcional)

### Arquivo Contábil (fcontabilidade.xlsx)
Colunas esperadas:
- Cliente
- Valor
- Saldo

### Base Geral (base_geral.xlsx)
Colunas esperadas:
- Cliente
- NF
- Valor
- Data
- Débito
- Crédito
- Histórico

---

## 🐛 Troubleshooting

### Erro de CORS
Se aparecer erro de CORS, verifique o backend:

```python
# backend/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Adicione sua origem
    ...
)
```

### API não responde
1. Verifique se o backend está rodando: http://localhost:8000
2. Verifique a URL no frontend (App.jsx linha 6)
3. Veja os logs do terminal do backend

### Arquivos não carregam
1. Verifique o formato (.xlsx, .xls, .csv)
2. Verifique o tamanho (máx 50MB)
3. Veja o console do navegador (F12)

---

## 📝 TODO - Próximos Passos

### Backend
- [ ] Implementar detecção de duplicatas com ML
- [ ] Implementar matching inteligente
- [ ] Integrar com Claude IA para análise
- [ ] Adicionar banco de dados para histórico
- [ ] Adicionar autenticação JWT
- [ ] Adicionar cache com Redis
- [ ] Adicionar testes unitários

### Frontend
- [ ] Adicionar página de resultados detalhados
- [ ] Adicionar visualização de duplicatas
- [ ] Adicionar gráficos com recharts
- [ ] Adicionar exportação de relatórios
- [ ] Adicionar histórico de processamentos
- [ ] Adicionar testes com Jest

---

## 🔐 Segurança

**IMPORTANTE:** 
- Nunca commite sua chave da API do Claude
- Use variáveis de ambiente para chaves sensíveis
- Adicione validação de tipos de arquivo no backend
- Limite o tamanho de arquivos
- Implemente rate limiting
- Use HTTPS em produção

Exemplo de uso seguro:

```python
# backend/.env
ANTHROPIC_API_KEY=sua-chave-secreta

# backend/main.py
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
```

---

## 📦 Build para Produção

### Frontend
```bash
npm run build
# Arquivos em: dist/
```

### Backend
```bash
# Use gunicorn para produção
pip install gunicorn
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## 🎯 Exemplo de Uso Completo

```bash
# Terminal 1 - Backend
cd backend
python main.py

# Terminal 2 - Frontend
npm run dev

# Terminal 3 - Teste com curl
curl -X POST http://localhost:8000/api/conciliacao/processar \
  -F "arquivo_origem=@financeiro.xlsx" \
  -F "arquivo_contabil=@fcontabilidade.xlsx" \
  -F "arquivo_geral_contabilidade=@base_geral.xlsx"
```

---

## 📞 Suporte

- Frontend funcionando: http://localhost:3000
- Backend funcionando: http://localhost:8000
- Docs da API: http://localhost:8000/docs

Logs úteis:
- Frontend: Console do navegador (F12)
- Backend: Terminal onde rodou `python main.py`

---

## 🎉 Pronto!

O sistema está 100% funcional e pronto para receber suas implementações personalizadas!

**Próximo passo:** Implementar a análise com Claude IA no backend! 🤖
