# 📊 Dashboard-Pipe-main — PipeCRM (Pipedrive + Sittax)

O **PipeCRM** é um portal/dashboard comercial (desktop) em **Python + Flet** para **consultar e acompanhar carteiras no Pipedrive**, cruzando informações com uma **base externa (Sittax) em Google Sheets**. O foco é dar visibilidade rápida de **pipeline, status, atrasos e saúde da carteira**, com filtros e exportação.

> Interface: `main.py` renderiza as telas no Flet (tema escuro) e consome as rotinas de dados de `service.py`.

## 🎯 Objetivo

Centralizar métricas de onboarding e performance comercial em um painel simples, para apoiar decisões do time (priorização de follow-ups, identificação de gargalos no funil, status financeiro/operacional etc.).

## 🧭 Como funciona (visão geral)

1. **Sittax (Google Sheets)**: o app carrega uma base estática via export CSV (configurável por `SITTAX_SHEET_ID` e `SITTAX_GID`).
2. **Pipedrive (API)**: ao selecionar o usuário, o app busca dados do Pipedrive (negócios/organizações/atividades) via token.
3. **Processamento e cruzamento**: os dados são normalizados (documento, valores, etapas, dias sem atividade/mudança de etapa) e cruzados com a base Sittax.
4. **Dashboard**: o usuário navega por lista, filtros, detalhes e gráficos; pode **atualizar** e **exportar Excel**.
5. **Cache local**: resultados do Pipedrive são cacheados em `storage/temp/pipedrive_cache/` para reduzir latência em cargas repetidas.

## ⚙️ Funcionalidades

- 🔐 Login por usuário do Pipedrive (lista + busca)
- 📋 Lista de clientes/negócios com filtros (texto, etapa, “dias sem atividade” / “dias sem mudar etapa”)
- 👁️ Detalhes do cliente (documento, etapa, status, mensalidade etc.)
- 📈 Gráficos (distribuição por etapa e por status)
- 🔄 Atualização manual (recarrega dados e respeita cache quando aplicável)
- 📤 Exportação de relatório para Excel (`.xlsx`)

## 🛠️ Tecnologias

- **Python 3.13+**
- **Flet 0.84** (UI desktop)
- **Pandas** (processamento)
- **Matplotlib** (gráficos)
- **Requests / Aiohttp** (integrações HTTP)
- **python-dotenv** (variáveis de ambiente via `.env`)

## ✅ Requisitos

- Windows (recomendado para execução desktop com Flet)
- Python 3.13+
- Token válido da API do Pipedrive com permissões/visibilidade para ler dados necessários
- Acesso à internet (Pipedrive + Google Sheets)

## 🚀 Como executar (Windows)

```bash
# 1) Criar ambiente virtual
python -m venv .venv

# 2) Ativar ambiente
.venv\\Scripts\\activate

# 3) Instalar dependências
pip install -r requirements.txt

# 4) Configurar variáveis (ver seção "Configuração")

# 5) Rodar
python main.py
```

## 🔐 Configuração

Crie um arquivo `.env` (use `.env.example` como base):

```env
PIPEDRIVE_API_TOKEN=seu_token_aqui

# Opcional — Base Sittax (Google Sheets)
SITTAX_SHEET_ID=1aEs_lFrTHuKW_rRx9ZNvfM-1m9mm74-Z5dWlbWpIqo0
SITTAX_GID=0
```

Alternativa (PowerShell) para testar sem `.env`:

```powershell
$env:PIPEDRIVE_API_TOKEN="seu_token_aqui"
python main.py
```

## 🔒 Segurança

- Não versionar tokens/segredos (`.env` já está no `.gitignore`).
- Em ambientes compartilhados/publicação, evite qualquer fallback de token no código e use apenas variáveis de ambiente.

## 📁 Estrutura do projeto

```text
Dashboard-Pipe-main/
├── main.py                       # App Flet (telas, navegação, exportação)
├── service.py                    # Integração Pipedrive + carga Sittax + cache + processamento
├── utils.py                      # Normalização/formatadores + render Matplotlib -> Image (Flet 0.84+)
├── views/                        # Componentes de tela reutilizáveis
│   ├── login.py                  # Tela de login simples (dropdown)
│   ├── dashboard.py              # Lista + filtros + tabs
│   ├── charts.py                 # Cards de gráficos (Matplotlib)
│   └── details.py                # Dialog de detalhes do cliente
├── storage/temp/pipedrive_cache/ # Cache local de consultas (arquivos .pkl)
├── SittaxPortal.spec             # Receita de build (PyInstaller)
└── README.md
```

## 🧩 Principais conceitos de dados

- **Key**: chave de cruzamento (preferencialmente CPF/CNPJ normalizado); quando ausente na planilha, pode haver fallback.
- **Dias_Sem_Ativ**: dias desde a última atividade/atualização (para priorização de follow-up).
- **Dias_Sem_Etapa**: dias desde a última mudança de etapa (para detectar estagnação no funil).
- **Status**: pode vir do Pipedrive e/ou Sittax (dependendo do merge e disponibilidade de dados).

## 🧱 Build (opcional)

Existe uma especificação para empacotar o app via PyInstaller:

```bash
pip install pyinstaller
pyinstaller SittaxPortal.spec
```

## 🩺 Troubleshooting rápido

- **“Nenhum dado encontrado”**: o token pode não ter visibilidade para a carteira do usuário selecionado, ou não há negócios retornados para aquele dono.
- **Aviso de base Sittax**: se `service.LAST_SITTAX_ERROR` indicar falha/HTTP 410, revise `SITTAX_SHEET_ID`/`SITTAX_GID` e o acesso/estado da planilha.
- **Exportação `.xlsx` falhando**: confirme dependências de Excel (`openpyxl`) instaladas (já incluídas em `requirements.txt`).

## 🏢 Sobre

Projeto desenvolvido por **Setupe Tecnologia**, focado em soluções de automação, integração e inteligência de dados para empresas.

## 📌 Status

🚧 Em desenvolvimento / evolução contínua
