# ForexBot v2 — Tarefas de Desenvolvimento

> Repo privado GitHub · cTrader Open API · Python · Django · Telegram
> 3 estratégias em paralelo · 24 pares · conta demo primeiro

---

## ⚠️ Importante — Dev vs Runtime

| O que fazer | Onde |
|---|---|
| Escrever código, editar ficheiros | Mac (dev) |
| `git add` / `git commit` / `git push` | Mac (dev) |
| Instalar dependências (`pip install`) | **VPS Linux** apenas |
| Autenticação OAuth cTrader | **VPS Linux** apenas |
| Correr o bot 24/7 | **VPS Linux** apenas |
| Ver o dashboard no browser | Browser → acede à VPS via IP |

A biblioteca `ctrader-open-api` usa Twisted com TCP nativo e **não funciona no Mac**.
O código é escrito no Mac e enviado para a VPS via `git push` → `git pull`.
**Não instalar dependências nem criar venv no Mac** — usar `scripts/setup_vps.sh` na VPS.

### `requirements.txt`

Um único ficheiro de dependências, instalado **apenas na VPS**:
```
ctrader-open-api==2.0.0
twisted==23.10.0
protobuf==4.25.3
pandas==2.2.2
numpy==1.26.4
pandas-ta==0.3.14b0
django==5.0.6
whitenoise==6.7.0
python-telegram-bot==21.3
python-dotenv==1.0.1
requests==2.32.3
structlog==24.2.0
pytest==8.2.2
pytest-asyncio==0.23.7
pytz==2024.1
schedule==1.2.2
```

### Fluxo de trabalho diário

```
Mac                          VPS Linux
─────                        ─────────
Editar código          →     
git push               →     git pull
                       →     python scripts/connect_check.py
                       →     python run_bot.py
Ver logs no terminal   ←     tail -f logs/decisions/2026-06-28.jsonl
Ver dashboard          ←     http://IP_DA_VPS:8000
```

---

## 🚦 Ponto mínimo para primeiro teste

> **A app pode ser testada a partir da Etapa 2.3.3**
>
> Nesse momento tens ligação ao cTrader confirmada, símbolos a carregar
> e velas a chegar. Tudo o resto são camadas em cima disso.
>
> Checklist do ponto mínimo (tudo na VPS):
> - [ ] `.env` preenchido com Client ID, Secret, Account ID, tokens OAuth
> - [ ] `pip install -r requirements.txt` concluído
> - [ ] `python -m forexbot.broker.ctrader_auth` executado com sucesso
> - [ ] `python scripts/connect_check.py` imprime símbolos e velas ✅
>
> Só depois avançar para as estratégias e o dashboard.

---

## FASE 0 — Preparar a VPS Linux

> Fazer isto **antes** de qualquer outra fase. A VPS tem de estar pronta
> para receber o código do Mac via git.

### Etapa 0.1 — Acesso e configuração inicial da VPS

- [ ] **0.1.1** Ligar à VPS via SSH do Mac
  ```bash
  ssh utilizador@IP_DA_VPS
  # exemplo: ssh root@123.456.789.0
  ```

- [ ] **0.1.2** Atualizar o sistema
  ```bash
  apt update && apt upgrade -y
  ```

- [ ] **0.1.3** Instalar Python 3.11+ e dependências do sistema
  ```bash
  apt install -y python3 python3-pip python3-venv git curl
  python3 --version   # deve ser 3.11 ou superior
  ```

- [ ] **0.1.4** Configurar chave SSH do Mac para acesso sem password à VPS
  ```bash
  # No Mac:
  ssh-keygen -t ed25519 -C "forexbot-vps"
  ssh-copy-id utilizador@IP_DA_VPS
  # Testar: ssh utilizador@IP_DA_VPS (não deve pedir password)
  ```

### Etapa 0.2 — Configurar Git na VPS

- [ ] **0.2.1** Configurar git na VPS
  ```bash
  git config --global user.name "Bruno Coelho"
  git config --global user.email "o_teu_email@exemplo.com"
  ```

- [ ] **0.2.2** Gerar chave SSH na VPS e adicionar ao GitHub
  ```bash
  # Na VPS:
  ssh-keygen -t ed25519 -C "forexbot-vps-github"
  cat ~/.ssh/id_ed25519.pub
  # Copiar o output e adicionar em:
  # github.com → Settings → SSH and GPG keys → New SSH key
  ```

- [ ] **0.2.3** Clonar o repositório na VPS
  ```bash
  cd /home/utilizador
  git clone git@github.com:BrunoKorpuzCoelho/ForexBotV2.git
  cd ForexBotV2
  ```

### Etapa 0.3 — Ambiente virtual na VPS

- [ ] **0.3.1** Criar e ativar venv na VPS
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

- [ ] **0.3.2** Instalar dependências completas na VPS
  ```bash
  pip install -r requirements.txt
  # Deve instalar ctrader-open-api, twisted, etc. sem erros
  ```

- [ ] **0.3.3** Verificar instalação do ctrader
  ```bash
  python -c "from ctrader_open_api import Client; print('✅ ctrader-open-api instalado')"
  ```

### Etapa 0.4 — Script de deploy Mac → VPS

- [ ] **0.4.1** Criar `scripts/deploy.sh` no Mac para automatizar o deploy
  ```bash
  #!/bin/bash
  # scripts/deploy.sh
  # Correr no Mac: bash scripts/deploy.sh
  # Envia o código para a VPS e reinicia o bot

  VPS_USER="utilizador"
  VPS_IP="IP_DA_VPS"
  VPS_PATH="/home/utilizador/ForexBotV2"
  SERVICE_BOT="forexbot"
  SERVICE_DASH="forexbot-dashboard"

  echo "📦 A fazer push para GitHub..."
  git push origin main

  echo "🔄 A fazer pull na VPS..."
  ssh $VPS_USER@$VPS_IP "cd $VPS_PATH && git pull origin main"

  echo "🔁 A reiniciar serviços na VPS..."
  ssh $VPS_USER@$VPS_IP "sudo systemctl restart $SERVICE_BOT $SERVICE_DASH"

  echo "✅ Deploy concluído!"
  echo "📋 Logs em tempo real:"
  ssh $VPS_USER@$VPS_IP "sudo journalctl -u $SERVICE_BOT -f --no-pager"
  ```

- [ ] **0.4.2** Dar permissão de execução ao script
  ```bash
  chmod +x scripts/deploy.sh
  ```

---

## FASE 1 — Estrutura base do projeto

### Etapa 1.1 — Criar repositório e estrutura de pastas

- [ ] **1.1.1** Criar repositório privado no GitHub com o nome `ForexBotV2`
  - Ir a github.com → New repository
  - Nome: `ForexBotV2`
  - Visibilidade: **Private**
  - Inicializar com README: sim
  - Adicionar `.gitignore` para Python

- [ ] **1.1.2** Clonar o repositório localmente
  ```bash
  git clone https://github.com/BrunoKorpuzCoelho/ForexBotV2.git
  cd ForexBotV2
  ```

- [ ] **1.1.3** Criar estrutura de pastas do projeto
  ```bash
  mkdir -p forexbot/{core,strategies,broker,dashboard,notifications,logs,tests}
  mkdir -p forexbot/strategies/{strategy_a,strategy_b,strategy_c}
  mkdir -p forexbot/dashboard/{templates,static}
  touch forexbot/__init__.py
  touch forexbot/core/__init__.py
  touch forexbot/strategies/__init__.py
  touch forexbot/broker/__init__.py
  touch forexbot/dashboard/__init__.py
  touch forexbot/notifications/__init__.py
  touch forexbot/tests/__init__.py
  ```

  Estrutura final esperada:
  ```
  ForexBotV2/
  ├── .env                          ← único ficheiro de config (vai para git, repo privado)
  ├── .gitignore
  ├── requirements.txt
  ├── README.md
  ├── TASKS.md                      ← este ficheiro
  ├── run_bot.py                    ← ponto de entrada principal
  ├── run_dashboard.py              ← arrancar o dashboard Django
  ├── forexbot/
  │   ├── __init__.py
  │   ├── config.py                 ← lê variáveis do .env
  │   ├── core/
  │   │   ├── __init__.py
  │   │   ├── candle.py             ← modelo Candle (OHLCV)
  │   │   ├── signal.py             ← modelo TradeSignal
  │   │   ├── decision_logger.py    ← regista TODAS as decisões
  │   │   ├── risk_manager.py       ← lot size, SL/TP
  │   │   └── main_loop.py          ← loop principal M15
  │   ├── strategies/
  │   │   ├── __init__.py
  │   │   ├── base.py               ← interface base de estratégia
  │   │   ├── strategy_a/           ← EMA Crossover + RSI
  │   │   │   ├── __init__.py
  │   │   │   └── strategy.py
  │   │   ├── strategy_b/           ← Bollinger Bands + RSI
  │   │   │   ├── __init__.py
  │   │   │   └── strategy.py
  │   │   └── strategy_c/           ← ORB Opening Range Breakout
  │   │       ├── __init__.py
  │   │       └── strategy.py
  │   ├── broker/
  │   │   ├── __init__.py
  │   │   ├── ctrader_client.py     ← ligação TCP cTrader
  │   │   ├── ctrader_auth.py       ← OAuth2 token
  │   │   └── ctrader_broker.py     ← abrir/fechar ordens
  │   ├── dashboard/
  │   │   ├── __init__.py
  │   │   ├── models.py             ← Trade, DecisionLog, EquityCurve
  │   │   ├── views.py              ← páginas do dashboard
  │   │   ├── urls.py
  │   │   └── templates/
  │   │       └── dashboard.html
  │   ├── notifications/
  │   │   ├── __init__.py
  │   │   └── telegram.py           ← enviar mensagens Telegram
  │   └── tests/
  │       ├── __init__.py
  │       ├── test_strategy_a.py
  │       ├── test_strategy_b.py
  │       └── test_strategy_c.py
  └── logs/
      ├── decisions/                 ← log por ciclo M15
      └── trades/                    ← log de trades abertos/fechados
  ```

---

### Etapa 1.2 — Ambiente virtual e dependências

- [ ] **1.2.1** Criar ambiente virtual Python (na VPS)
  ```bash
  bash scripts/setup_vps.sh
  # ou manualmente:
  python3 -m venv venv
  source venv/bin/activate
  ```

- [ ] **1.2.2** Criar `requirements.txt` com todas as bibliotecas necessárias
  ```
  # requirements.txt

  # cTrader Open API
  ctrader-open-api==2.0.0
  twisted==23.10.0
  protobuf==4.25.3

  # Indicadores técnicos (EMA, RSI, Bollinger Bands, ATR)
  pandas==2.2.2
  numpy==1.26.4
  pandas-ta==0.3.14b0

  # Dashboard Web
  django==5.0.6
  whitenoise==6.7.0

  # Telegram
  python-telegram-bot==21.3

  # Variáveis de ambiente
  python-dotenv==1.0.1

  # HTTP requests (para refresh de token OAuth)
  requests==2.32.3

  # Logging estruturado
  structlog==24.2.0

  # Testes
  pytest==8.2.2
  pytest-asyncio==0.23.7

  # Utilitários
  pytz==2024.1
  schedule==1.2.2
  ```

- [ ] **1.2.3** Instalar todas as dependências
  ```bash
  pip install -r requirements.txt
  ```

- [ ] **1.2.4** Verificar que tudo instalou corretamente
  ```bash
  pip list | grep -E "ctrader|pandas|django|telegram|dotenv"
  ```

---

### Etapa 1.3 — Ficheiro `.env`

> O `.env` vai para o git porque o repositório é **privado**.
> Nunca tornar o repositório público com este ficheiro.

- [ ] **1.3.1** Criar o ficheiro `.env` na raiz do projeto com todas as variáveis necessárias

  ```env
  # .env — ForexBot v2
  # ATENÇÃO: repositório PRIVADO. Nunca tornar público.

  # ─────────────────────────────────────────
  # cTrader Open API
  # ─────────────────────────────────────────
  # Obtidos em: https://openapi.ctrader.com/apps
  CTRADER_CLIENT_ID=cole_aqui_o_client_id
  CTRADER_CLIENT_SECRET=cole_aqui_o_client_secret

  # ID da conta demo (ver no cTrader depois de autenticar)
  CTRADER_ACCOUNT_ID=cole_aqui_o_account_id

  # Tokens OAuth (gerados automaticamente pelo script de auth)
  CTRADER_ACCESS_TOKEN=
  CTRADER_REFRESH_TOKEN=

  # Servidor (demo para testes, live para produção)
  CTRADER_HOST=demo.ctraderapi.com
  CTRADER_PORT=5035

  # ─────────────────────────────────────────
  # Telegram
  # ─────────────────────────────────────────
  # Criar bot em @BotFather no Telegram
  TELEGRAM_BOT_TOKEN=cole_aqui_o_token_do_bot
  # Obter o chat_id enviando mensagem ao bot e indo a:
  # https://api.telegram.org/bot<TOKEN>/getUpdates
  TELEGRAM_CHAT_ID=cole_aqui_o_chat_id

  # ─────────────────────────────────────────
  # Bot — Modo de operação
  # ─────────────────────────────────────────
  # true = não envia ordens reais (só simula e loga)
  # false = envia ordens reais para a conta demo
  DRY_RUN=true

  # Nível de log: DEBUG, INFO, WARNING, ERROR
  LOG_LEVEL=INFO

  # ─────────────────────────────────────────
  # Gestão de risco
  # ─────────────────────────────────────────
  # Percentagem do equity a arriscar por trade (ex: 1.0 = 1%)
  RISK_PCT=1.0

  # ─────────────────────────────────────────
  # Django Dashboard
  # ─────────────────────────────────────────
  DJANGO_SECRET_KEY=muda_esta_chave_para_algo_aleatorio_longo
  DJANGO_DEBUG=True
  DJANGO_PORT=8000

  # ─────────────────────────────────────────
  # Estratégias — ativar/desativar
  # ─────────────────────────────────────────
  STRATEGY_A_ENABLED=true
  STRATEGY_B_ENABLED=true
  STRATEGY_C_ENABLED=true

  # ─────────────────────────────────────────
  # Pares de moeda ativos
  # ─────────────────────────────────────────
  # Separados por vírgula, exatamente como aparecem no cTrader
  SYMBOLS=EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,EURGBP,EURJPY,GBPJPY,AUDJPY,EURAUD,GBPCHF,EURCHF,XAUUSD,XAGUSD,XTIUSD,BTCUSD,ETHUSD,SOLUSD,XRPUSD
  ```

- [ ] **1.3.2** Verificar que o `.gitignore` **NÃO** ignora o `.env`
  - Abrir `.gitignore` e remover a linha `.env` se existir
  - Adicionar em vez disso o ficheiro `.env.example` (versão sem valores reais) para documentação

- [ ] **1.3.3** Criar `.env.example` para documentação (este sim pode ser público)
  - Copiar o `.env` mas apagar todos os valores reais
  - Deixar apenas os nomes das variáveis como guia

---

### Etapa 1.4 — Ficheiro de configuração central

- [ ] **1.4.1** Criar `forexbot/config.py` que lê o `.env` e expõe todas as variáveis

  ```python
  # forexbot/config.py
  import os
  from dotenv import load_dotenv

  load_dotenv()

  # ── cTrader ──────────────────────────────────────────────
  CTRADER_CLIENT_ID     = os.getenv("CTRADER_CLIENT_ID", "")
  CTRADER_CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET", "")
  CTRADER_ACCOUNT_ID    = int(os.getenv("CTRADER_ACCOUNT_ID", "0"))
  CTRADER_ACCESS_TOKEN  = os.getenv("CTRADER_ACCESS_TOKEN", "")
  CTRADER_REFRESH_TOKEN = os.getenv("CTRADER_REFRESH_TOKEN", "")
  CTRADER_HOST          = os.getenv("CTRADER_HOST", "demo.ctraderapi.com")
  CTRADER_PORT          = int(os.getenv("CTRADER_PORT", "5035"))

  # ── Telegram ─────────────────────────────────────────────
  TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
  TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID", "")

  # ── Bot ──────────────────────────────────────────────────
  DRY_RUN   = os.getenv("DRY_RUN", "true").lower() == "true"
  LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

  # ── Risco ────────────────────────────────────────────────
  RISK_PCT = float(os.getenv("RISK_PCT", "1.0"))

  # ── Django ───────────────────────────────────────────────
  DJANGO_SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me")
  DJANGO_DEBUG      = os.getenv("DJANGO_DEBUG", "True") == "True"
  DJANGO_PORT       = int(os.getenv("DJANGO_PORT", "8000"))

  # ── Estratégias ──────────────────────────────────────────
  STRATEGY_A_ENABLED = os.getenv("STRATEGY_A_ENABLED", "true").lower() == "true"
  STRATEGY_B_ENABLED = os.getenv("STRATEGY_B_ENABLED", "true").lower() == "true"
  STRATEGY_C_ENABLED = os.getenv("STRATEGY_C_ENABLED", "true").lower() == "true"

  # ── Pares ────────────────────────────────────────────────
  SYMBOLS = [s.strip() for s in os.getenv("SYMBOLS", "EURUSD,XAUUSD").split(",")]

  # ── Validação no arranque ─────────────────────────────────
  def validate():
      errors = []
      if not CTRADER_CLIENT_ID:
          errors.append("CTRADER_CLIENT_ID em falta no .env")
      if not CTRADER_CLIENT_SECRET:
          errors.append("CTRADER_CLIENT_SECRET em falta no .env")
      if not CTRADER_ACCOUNT_ID:
          errors.append("CTRADER_ACCOUNT_ID em falta no .env")
      if not TELEGRAM_BOT_TOKEN:
          errors.append("TELEGRAM_BOT_TOKEN em falta no .env")
      if not TELEGRAM_CHAT_ID:
          errors.append("TELEGRAM_CHAT_ID em falta no .env")
      if errors:
          raise EnvironmentError(
              "Erros de configuração no .env:\n" + "\n".join(f"  ❌ {e}" for e in errors)
          )
      print("✅ Configuração validada com sucesso")

  if __name__ == "__main__":
      validate()
  ```

- [ ] **1.4.2** Testar a configuração
  ```bash
  python forexbot/config.py
  # Deve imprimir: ✅ Configuração validada com sucesso
  # Ou listar os erros em falta
  ```

---

## FASE 2 — Ligação ao cTrader

### Etapa 2.1 — Registar a app no cTrader

- [ ] **2.1.1** Ir a `https://openapi.ctrader.com/apps` e fazer login com cTrader ID

- [ ] **2.1.2** Criar nova aplicação
  - Nome: `ForexBotV2`
  - Descrição: `Bot de trading automatizado multi-estratégia para conta demo`
  - Redirect URI: `http://localhost:8080/callback`
  - Aguardar aprovação por email da Spotware

- [ ] **2.1.3** Após aprovação, copiar `Client ID` e `Client Secret` para o `.env`

---

### Etapa 2.2 — Autenticação OAuth2

- [ ] **2.2.1** Criar `forexbot/broker/ctrader_auth.py`

  ```python
  # forexbot/broker/ctrader_auth.py
  """
  Gera e renova tokens OAuth2 para o cTrader Open API.
  Correr uma vez manualmente: python -m forexbot.broker.ctrader_auth
  """
  import os
  import requests
  import webbrowser
  from http.server import HTTPServer, BaseHTTPRequestHandler
  from urllib.parse import urlparse, parse_qs
  from dotenv import load_dotenv, set_key

  load_dotenv()

  CLIENT_ID     = os.getenv("CTRADER_CLIENT_ID")
  CLIENT_SECRET = os.getenv("CTRADER_CLIENT_SECRET")
  REDIRECT_URI  = "http://localhost:8080/callback"
  AUTH_URL      = "https://connect.spotware.com/apps/auth"
  TOKEN_URL     = "https://connect.spotware.com/apps/token"
  ENV_FILE      = ".env"

  # Servidor local temporário para capturar o código OAuth
  _auth_code = None

  class CallbackHandler(BaseHTTPRequestHandler):
      def do_GET(self):
          global _auth_code
          params = parse_qs(urlparse(self.path).query)
          _auth_code = params.get("code", [None])[0]
          self.send_response(200)
          self.end_headers()
          self.wfile.write(b"<h2>Autenticado! Podes fechar esta janela.</h2>")

      def log_message(self, format, *args):
          pass  # silenciar logs do servidor HTTP

  def get_auth_url():
      return (
          f"{AUTH_URL}?response_type=code"
          f"&client_id={CLIENT_ID}"
          f"&redirect_uri={REDIRECT_URI}"
          f"&scope=trading"
      )

  def exchange_code_for_tokens(code: str) -> dict:
      resp = requests.post(TOKEN_URL, data={
          "grant_type":    "authorization_code",
          "code":          code,
          "redirect_uri":  REDIRECT_URI,
          "client_id":     CLIENT_ID,
          "client_secret": CLIENT_SECRET,
      })
      resp.raise_for_status()
      return resp.json()

  def refresh_token_if_needed() -> str:
      """Renova o access token usando o refresh token. Chamado automaticamente pelo broker."""
      refresh = os.getenv("CTRADER_REFRESH_TOKEN", "")
      if not refresh:
          raise RuntimeError("Sem refresh token. Correr: python -m forexbot.broker.ctrader_auth")

      resp = requests.post(TOKEN_URL, data={
          "grant_type":    "refresh_token",
          "refresh_token": refresh,
          "client_id":     CLIENT_ID,
          "client_secret": CLIENT_SECRET,
      })
      resp.raise_for_status()
      data = resp.json()

      # Guardar novos tokens no .env
      set_key(ENV_FILE, "CTRADER_ACCESS_TOKEN",  data["access_token"])
      set_key(ENV_FILE, "CTRADER_REFRESH_TOKEN",  data["refresh_token"])
      os.environ["CTRADER_ACCESS_TOKEN"]  = data["access_token"]
      os.environ["CTRADER_REFRESH_TOKEN"] = data["refresh_token"]

      print("✅ Token renovado com sucesso")
      return data["access_token"]

  if __name__ == "__main__":
      print("A abrir browser para autenticação cTrader...")
      webbrowser.open(get_auth_url())

      print("A aguardar callback em http://localhost:8080/callback ...")
      server = HTTPServer(("localhost", 8080), CallbackHandler)
      server.handle_request()  # uma só request

      if not _auth_code:
          print("❌ Não foi recebido código de autenticação")
          exit(1)

      print(f"✅ Código recebido: {_auth_code[:10]}...")
      tokens = exchange_code_for_tokens(_auth_code)

      set_key(ENV_FILE, "CTRADER_ACCESS_TOKEN",  tokens["access_token"])
      set_key(ENV_FILE, "CTRADER_REFRESH_TOKEN",  tokens["refresh_token"])

      print("✅ Tokens guardados no .env com sucesso!")
      print(f"   Access token:  {tokens['access_token'][:20]}...")
      print(f"   Refresh token: {tokens['refresh_token'][:20]}...")
  ```

- [ ] **2.2.2** Correr o script de autenticação (apenas uma vez)
  ```bash
  python -m forexbot.broker.ctrader_auth
  # Vai abrir o browser, fazer login, e guardar os tokens no .env automaticamente
  ```

---

### Etapa 2.3 — Cliente TCP cTrader

- [ ] **2.3.1** Criar `forexbot/broker/ctrader_client.py`

  ```python
  # forexbot/broker/ctrader_client.py
  """
  Cliente TCP síncrono para o cTrader Open API via Twisted.
  Gere a ligação, autenticação da app, e pedidos de dados.
  """
  import threading
  import time
  import logging
  from ctrader_open_api import Client, Protobuf, TcpProtocol, EndPoints
  from ctrader_open_api.messages.OpenApiCommonMessages_pb2 import ProtoHeartbeatEvent
  from ctrader_open_api.messages.OpenApiMessages_pb2 import (
      ProtoOAApplicationAuthReq,
      ProtoOAApplicationAuthRes,
      ProtoOAAccountAuthReq,
      ProtoOAAccountAuthRes,
      ProtoOAGetTrendbarsReq,
      ProtoOAGetTrendbarsRes,
      ProtoOAReconcileReq,
      ProtoOAReconcileRes,
      ProtoOANewOrderReq,
      ProtoOAClosePositionReq,
      ProtoOAGetSymbolsReq,
      ProtoOAGetSymbolsRes,
  )
  from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
  from twisted.internet import reactor
  from forexbot import config

  log = logging.getLogger(__name__)

  PERIOD_MAP = {
      "M1":  ProtoOATrendbarPeriod.M1,
      "M5":  ProtoOATrendbarPeriod.M5,
      "M15": ProtoOATrendbarPeriod.M15,
      "H1":  ProtoOATrendbarPeriod.H1,
      "H4":  ProtoOATrendbarPeriod.H4,
      "D1":  ProtoOATrendbarPeriod.D1,
  }

  class CTraderClient:
      """
      Wrapper síncrono sobre o cliente Twisted assíncrono do cTrader.
      Corre o reactor numa thread daemon separada.
      """

      def __init__(self, access_token: str):
          self._token     = access_token
          self._connected = False
          self._authed    = False
          self._symbols   = {}       # nome → symbol_id
          self._pending   = {}       # clientMsgId → resultado
          self._lock      = threading.Event()

          self._client = Client(
              config.CTRADER_HOST,
              config.CTRADER_PORT,
              TcpProtocol
          )
          self._client.setConnectedCallback(self._on_connected)
          self._client.setDisconnectedCallback(self._on_disconnected)
          self._client.setMessageReceivedCallback(self._on_message)

      def start(self):
          """Arranca o reactor em thread daemon e aguarda autenticação."""
          self._client.startService()
          t = threading.Thread(target=reactor.run, kwargs={"installSignalHandlers": False}, daemon=True)
          t.start()
          # Aguardar até estar autenticado (máx 30 segundos)
          if not self._lock.wait(timeout=30):
              raise TimeoutError("cTrader: timeout na autenticação (30s)")
          log.info("cTrader client pronto")

      def _on_connected(self, client):
          log.info("TCP ligado — a autenticar app...")
          req = ProtoOAApplicationAuthReq()
          req.clientId     = config.CTRADER_CLIENT_ID
          req.clientSecret = config.CTRADER_CLIENT_SECRET
          client.send(req)

      def _on_disconnected(self, client, reason):
          log.warning(f"cTrader desligado: {reason}")
          self._connected = False
          self._authed    = False

      def _on_message(self, client, message):
          msg_type = message.payloadType

          if msg_type == ProtoOAApplicationAuthRes().payloadType:
              log.info("App autenticada — a autenticar conta...")
              req = ProtoOAAccountAuthReq()
              req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
              req.accessToken         = self._token
              client.send(req)

          elif msg_type == ProtoOAAccountAuthRes().payloadType:
              log.info(f"Conta {config.CTRADER_ACCOUNT_ID} autenticada ✅")
              self._connected = True
              self._authed    = True
              self._lock.set()  # liberta o start()

          elif msg_type == ProtoOAGetSymbolsRes().payloadType:
              res = Protobuf.extract(message, ProtoOAGetSymbolsRes)
              for sym in res.symbol:
                  self._symbols[sym.symbolName] = sym.symbolId
              log.info(f"{len(self._symbols)} símbolos carregados")
              # Guardar resultado para quem estava à espera
              key = f"symbols"
              if key in self._pending:
                  self._pending[key] = self._symbols.copy()

          elif msg_type == ProtoOAGetTrendbarsRes().payloadType:
              res = Protobuf.extract(message, ProtoOAGetTrendbarsRes)
              key = f"bars_{res.symbolId}"
              if key in self._pending:
                  self._pending[key] = list(res.trendbar)

      def get_symbol_id(self, symbol: str) -> int | None:
          return self._symbols.get(symbol)

      def load_symbols(self):
          """Carrega todos os símbolos disponíveis na conta."""
          req = ProtoOAGetSymbolsReq()
          req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
          key = "symbols"
          self._pending[key] = None
          self._client.send(req)
          # Aguardar resposta
          for _ in range(100):
              if self._pending.get(key) is not None:
                  return self._pending.pop(key)
              time.sleep(0.1)
          raise TimeoutError("Timeout ao carregar símbolos")

      def get_candles(self, symbol: str, timeframe: str = "M15", count: int = 200) -> list:
          """Obtém velas históricas para o símbolo e timeframe indicados."""
          sym_id = self.get_symbol_id(symbol)
          if sym_id is None:
              log.warning(f"Símbolo não encontrado: {symbol}")
              return []

          period = PERIOD_MAP.get(timeframe, ProtoOATrendbarPeriod.M15)
          req = ProtoOAGetTrendbarsReq()
          req.ctidTraderAccountId = config.CTRADER_ACCOUNT_ID
          req.symbolId            = sym_id
          req.period              = period
          req.count               = count

          key = f"bars_{sym_id}"
          self._pending[key] = None
          self._client.send(req)

          for _ in range(100):
              if self._pending.get(key) is not None:
                  return self._pending.pop(key)
              time.sleep(0.1)

          log.warning(f"Timeout ao obter velas para {symbol}")
          return []
  ```

- [ ] **2.3.2** Criar script de teste de ligação `scripts/connect_check.py`

  ```python
  # scripts/connect_check.py
  """
  Testa a ligação ao cTrader.
  Correr: python scripts/connect_check.py
  Deve imprimir saldo da conta e 5 velas M15 do EURUSD.
  """
  import sys
  import os
  sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

  from forexbot import config
  from forexbot.broker.ctrader_client import CTraderClient

  def main():
      print("🔌 A ligar ao cTrader...")
      client = CTraderClient(config.CTRADER_ACCESS_TOKEN)
      client.start()
      print("✅ Ligado!")

      print("📋 A carregar símbolos...")
      symbols = client.load_symbols()
      print(f"✅ {len(symbols)} símbolos disponíveis")

      # Verificar se EURUSD existe
      for sym in ["EURUSD", "XAUUSD", "BTCUSD"]:
          sym_id = client.get_symbol_id(sym)
          status = f"✅ ID={sym_id}" if sym_id else "❌ NÃO ENCONTRADO"
          print(f"   {sym}: {status}")

      print("\n📊 A obter 5 velas M15 de EURUSD...")
      candles = client.get_candles("EURUSD", "M15", count=5)
      if candles:
          for c in candles[-5:]:
              print(f"   Open={c.low + c.open} High={c.low + c.high} "
                    f"Low={c.low} Close={c.low + c.close} Vol={c.volume}")
      else:
          print("❌ Sem velas recebidas — verificar símbolo ou token")

      print("\n✅ Teste concluído com sucesso!")

  if __name__ == "__main__":
      main()
  ```

- [ ] **2.3.3** Correr o teste de ligação
  ```bash
  python scripts/connect_check.py
  # Deve imprimir os símbolos e 5 velas EURUSD sem erros
  ```

---

## FASE 3 — Modelos base e Decision Logger

### Etapa 3.1 — Modelo Candle

- [ ] **3.1.1** Criar `forexbot/core/candle.py`

  ```python
  # forexbot/core/candle.py
  from dataclasses import dataclass
  from datetime import datetime

  @dataclass
  class Candle:
      timestamp: datetime
      open:  float
      high:  float
      low:   float
      close: float
      volume: float

      @property
      def body(self) -> float:
          return abs(self.close - self.open)

      @property
      def is_bullish(self) -> bool:
          return self.close > self.open

      @property
      def is_bearish(self) -> bool:
          return self.close < self.open

      def __repr__(self):
          d = self.timestamp.strftime("%Y-%m-%d %H:%M")
          return f"Candle({d} O={self.open:.5f} H={self.high:.5f} L={self.low:.5f} C={self.close:.5f})"
  ```

### Etapa 3.2 — Modelo TradeSignal

- [ ] **3.2.1** Criar `forexbot/core/signal.py`

  ```python
  # forexbot/core/signal.py
  from dataclasses import dataclass, field
  from datetime import datetime
  from enum import Enum
  import uuid

  class Direction(Enum):
      LONG  = "LONG"
      SHORT = "SHORT"

  @dataclass
  class TradeSignal:
      strategy:  str           # "A", "B", "C"
      symbol:    str           # "EURUSD"
      direction: Direction
      entry:     float
      sl:        float         # stop loss
      tp:        float         # take profit
      reason:    str           # texto legível: "EMA9 cruzou EMA21 ↑ · RSI=56.3"
      timestamp: datetime = field(default_factory=datetime.utcnow)
      id:        str      = field(default_factory=lambda: str(uuid.uuid4())[:8])

      @property
      def risk_pips(self) -> float:
          return abs(self.entry - self.sl)

      @property
      def reward_pips(self) -> float:
          return abs(self.tp - self.entry)

      @property
      def rr_ratio(self) -> float:
          if self.risk_pips == 0:
              return 0
          return round(self.reward_pips / self.risk_pips, 2)

      def __repr__(self):
          return (f"Signal({self.strategy} {self.symbol} {self.direction.value} "
                  f"E={self.entry} SL={self.sl} TP={self.tp} RR={self.rr_ratio})")
  ```

### Etapa 3.3 — Decision Logger

- [ ] **3.3.1** Criar `forexbot/core/decision_logger.py`
  > Esta é a peça mais importante. Regista TUDO o que o bot faz e porquê,
  > para poderes ver depois em detalhe o que aconteceu em cada ciclo.

  ```python
  # forexbot/core/decision_logger.py
  """
  Regista cada decisão do bot em ficheiro de log legível.
  Por cada ciclo M15 e par, grava:
    - valores dos indicadores
    - se entrou ou não
    - motivo exato da decisão
  """
  import os
  import json
  import logging
  from datetime import datetime, timezone
  from pathlib import Path
  from forexbot.core.signal import TradeSignal

  log = logging.getLogger(__name__)

  LOGS_DIR = Path("logs/decisions")
  LOGS_DIR.mkdir(parents=True, exist_ok=True)

  def _log_file(date: datetime) -> Path:
      return LOGS_DIR / f"{date.strftime('%Y-%m-%d')}.jsonl"

  def log_no_signal(
      strategy:   str,
      symbol:     str,
      reason:     str,
      indicators: dict,
      timestamp:  datetime | None = None,
  ):
      """
      Regista um ciclo onde NÃO houve sinal.
      Exemplo de indicators: {"ema9": 1.0845, "ema21": 1.0832, "rsi": 48.2}
      """
      ts = timestamp or datetime.now(timezone.utc)
      record = {
          "ts":         ts.isoformat(),
          "strategy":   strategy,
          "symbol":     symbol,
          "result":     "NO_SIGNAL",
          "reason":     reason,
          "indicators": indicators,
      }
      _write(record, ts)
      log.debug(f"[{strategy}][{symbol}] NO_SIGNAL — {reason}")

  def log_signal(signal: TradeSignal, indicators: dict):
      """
      Regista um ciclo onde houve sinal de entrada.
      """
      record = {
          "ts":         signal.timestamp.isoformat(),
          "strategy":   signal.strategy,
          "symbol":     signal.symbol,
          "result":     "SIGNAL",
          "direction":  signal.direction.value,
          "entry":      signal.entry,
          "sl":         signal.sl,
          "tp":         signal.tp,
          "rr":         signal.rr_ratio,
          "reason":     signal.reason,
          "indicators": indicators,
      }
      _write(record, signal.timestamp)
      log.info(f"[{signal.strategy}][{signal.symbol}] SIGNAL {signal.direction.value} "
               f"E={signal.entry} SL={signal.sl} TP={signal.tp} | {signal.reason}")

  def log_trade_open(signal: TradeSignal, lot: float, ticket: str):
      record = {
          "ts":       signal.timestamp.isoformat(),
          "strategy": signal.strategy,
          "symbol":   signal.symbol,
          "result":   "TRADE_OPEN",
          "ticket":   ticket,
          "direction":signal.direction.value,
          "entry":    signal.entry,
          "sl":       signal.sl,
          "tp":       signal.tp,
          "lot":      lot,
          "reason":   signal.reason,
      }
      _write(record, signal.timestamp)

  def log_trade_close(ticket: str, symbol: str, strategy: str,
                       pnl: float, pips: float, duration_min: int, exit_reason: str):
      ts = datetime.now(timezone.utc)
      record = {
          "ts":           ts.isoformat(),
          "strategy":     strategy,
          "symbol":       symbol,
          "result":       "TRADE_CLOSE",
          "ticket":       ticket,
          "pnl":          pnl,
          "pips":         pips,
          "duration_min": duration_min,
          "exit_reason":  exit_reason,
      }
      _write(record, ts)

  def _write(record: dict, ts: datetime):
      try:
          with open(_log_file(ts), "a", encoding="utf-8") as f:
              f.write(json.dumps(record, ensure_ascii=False) + "\n")
      except Exception as e:
          log.error(f"Erro ao escrever log: {e}")
  ```

---

## FASE 4 — Estratégias

### Etapa 4.1 — Interface base

- [ ] **4.1.1** Criar `forexbot/strategies/base.py`

  ```python
  # forexbot/strategies/base.py
  from abc import ABC, abstractmethod
  from forexbot.core.candle import Candle
  from forexbot.core.signal import TradeSignal

  class BaseStrategy(ABC):
      """Interface que todas as estratégias têm de implementar."""

      @property
      @abstractmethod
      def name(self) -> str:
          """Nome da estratégia: 'A', 'B', 'C'"""

      @abstractmethod
      def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
          """
          Avalia as velas e retorna um sinal ou None.
          Deve chamar decision_logger.log_no_signal() quando não há sinal.
          Deve chamar decision_logger.log_signal() quando há sinal.
          """
  ```

### Etapa 4.2 — Estratégia A (EMA Crossover + RSI)

- [ ] **4.2.1** Criar `forexbot/strategies/strategy_a/strategy.py`

  ```python
  # forexbot/strategies/strategy_a/strategy.py
  """
  Estratégia A — EMA Crossover + RSI

  Regras (simples, 2 condições):
    LONG:  EMA9 cruza EMA21 para CIMA   + RSI(14) > 50
    SHORT: EMA9 cruza EMA21 para BAIXO  + RSI(14) < 50

  SL:  swing low/high dos últimos 5 candles
  TP:  2× o risco (RR 1:2)
  TF:  M15
  """
  import pandas as pd
  import pandas_ta as ta
  import logging
  from forexbot.strategies.base import BaseStrategy
  from forexbot.core.candle import Candle
  from forexbot.core.signal import TradeSignal, Direction
  from forexbot.core import decision_logger as dl

  log = logging.getLogger(__name__)

  class StrategyA(BaseStrategy):

      @property
      def name(self) -> str:
          return "A"

      def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
          if len(candles) < 30:
              dl.log_no_signal("A", symbol, "candles insuficientes", {"count": len(candles)})
              return None

          # Converter para DataFrame
          df = pd.DataFrame([{
              "open":  c.open,
              "high":  c.high,
              "low":   c.low,
              "close": c.close,
          } for c in candles])

          # Calcular indicadores
          df["ema9"]  = ta.ema(df["close"], length=9)
          df["ema21"] = ta.ema(df["close"], length=21)
          df["rsi"]   = ta.rsi(df["close"], length=14)

          # Última vela completa (índice -2) e a anterior (-3) para detetar o cruzamento
          prev  = df.iloc[-3]
          curr  = df.iloc[-2]
          last_candle = candles[-2]

          ema9_curr  = curr["ema9"]
          ema21_curr = curr["ema21"]
          ema9_prev  = prev["ema9"]
          ema21_prev = prev["ema21"]
          rsi        = curr["rsi"]

          indicators = {
              "ema9":  round(ema9_curr, 5),
              "ema21": round(ema21_curr, 5),
              "rsi":   round(rsi, 2),
              "cross": "up" if ema9_curr > ema21_curr and ema9_prev <= ema21_prev else
                       "down" if ema9_curr < ema21_curr and ema9_prev >= ema21_prev else "none",
          }

          # ── Verificar cruzamento LONG ─────────────────────────
          crossed_up   = ema9_prev <= ema21_prev and ema9_curr > ema21_curr
          crossed_down = ema9_prev >= ema21_prev and ema9_curr < ema21_curr

          if crossed_up and rsi > 50:
              # Calcular SL e TP
              swing_low = min(c.low for c in candles[-6:-1])
              entry     = last_candle.close
              sl        = swing_low - 0.0002   # 2 pips de buffer
              tp        = entry + 2 * (entry - sl)
              reason    = f"EMA9 cruzou EMA21 ↑ · RSI={rsi:.1f}"
              signal = TradeSignal("A", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          if crossed_down and rsi < 50:
              swing_high = max(c.high for c in candles[-6:-1])
              entry      = last_candle.close
              sl         = swing_high + 0.0002
              tp         = entry - 2 * (sl - entry)
              reason     = f"EMA9 cruzou EMA21 ↓ · RSI={rsi:.1f}"
              signal = TradeSignal("A", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          # Sem sinal — registar motivo
          if crossed_up and rsi <= 50:
              reason = f"Cruzamento ↑ mas RSI={rsi:.1f} ≤ 50 (sem confirmação)"
          elif crossed_down and rsi >= 50:
              reason = f"Cruzamento ↓ mas RSI={rsi:.1f} ≥ 50 (sem confirmação)"
          else:
              reason = f"Sem cruzamento EMA · EMA9={ema9_curr:.5f} EMA21={ema21_curr:.5f}"

          dl.log_no_signal("A", symbol, reason, indicators)
          return None
  ```

### Etapa 4.3 — Estratégia B (Bollinger Bands + RSI)

- [ ] **4.3.1** Criar `forexbot/strategies/strategy_b/strategy.py`

  ```python
  # forexbot/strategies/strategy_b/strategy.py
  """
  Estratégia B — Bollinger Bands + RSI (Mean Reversion)

  Regras (2 condições):
    LONG:  close <= banda inferior (lower)  + RSI(14) < 35
    SHORT: close >= banda superior (upper)  + RSI(14) > 65

  SL:  1× ATR(14) abaixo/acima da entrada
  TP:  banda média (EMA20)
  TF:  M15
  """
  import pandas as pd
  import pandas_ta as ta
  import logging
  from forexbot.strategies.base import BaseStrategy
  from forexbot.core.candle import Candle
  from forexbot.core.signal import TradeSignal, Direction
  from forexbot.core import decision_logger as dl

  log = logging.getLogger(__name__)

  RSI_OVERSOLD  = 35
  RSI_OVERBOUGHT = 65

  class StrategyB(BaseStrategy):

      @property
      def name(self) -> str:
          return "B"

      def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
          if len(candles) < 30:
              dl.log_no_signal("B", symbol, "candles insuficientes", {"count": len(candles)})
              return None

          df = pd.DataFrame([{
              "high":  c.high,
              "low":   c.low,
              "close": c.close,
          } for c in candles])

          # Bollinger Bands (20, 2) e RSI(14) e ATR(14)
          bb  = ta.bbands(df["close"], length=20, std=2)
          rsi = ta.rsi(df["close"], length=14)
          atr = ta.atr(df["high"], df["low"], df["close"], length=14)

          if bb is None or rsi is None or atr is None:
              dl.log_no_signal("B", symbol, "indicadores não calculados", {})
              return None

          df = pd.concat([df, bb, rsi.rename("rsi"), atr.rename("atr")], axis=1)
          curr = df.iloc[-2]
          last_candle = candles[-2]

          lower  = curr["BBL_20_2.0"]
          middle = curr["BBM_20_2.0"]
          upper  = curr["BBU_20_2.0"]
          close  = curr["close"]
          rsi_v  = curr["rsi"]
          atr_v  = curr["atr"]

          indicators = {
              "close":  round(close, 5),
              "bb_low": round(lower, 5),
              "bb_mid": round(middle, 5),
              "bb_up":  round(upper, 5),
              "rsi":    round(rsi_v, 2),
              "atr":    round(atr_v, 5),
          }

          # ── LONG: preço na banda inferior + RSI oversold ──────
          if close <= lower and rsi_v < RSI_OVERSOLD:
              entry  = last_candle.close
              sl     = entry - atr_v
              tp     = middle
              reason = f"Preço ({close:.5f}) ≤ BB lower ({lower:.5f}) · RSI={rsi_v:.1f}"
              signal = TradeSignal("B", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          # ── SHORT: preço na banda superior + RSI overbought ───
          if close >= upper and rsi_v > RSI_OVERBOUGHT:
              entry  = last_candle.close
              sl     = entry + atr_v
              tp     = middle
              reason = f"Preço ({close:.5f}) ≥ BB upper ({upper:.5f}) · RSI={rsi_v:.1f}"
              signal = TradeSignal("B", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          # Sem sinal
          if close <= lower:
              reason = f"Preço na BB lower mas RSI={rsi_v:.1f} ≥ {RSI_OVERSOLD} (sem confirmação)"
          elif close >= upper:
              reason = f"Preço na BB upper mas RSI={rsi_v:.1f} ≤ {RSI_OVERBOUGHT} (sem confirmação)"
          else:
              reason = f"Preço ({close:.5f}) dentro das bandas [{lower:.5f}, {upper:.5f}]"

          dl.log_no_signal("B", symbol, reason, indicators)
          return None
  ```

### Etapa 4.4 — Estratégia C (ORB)

- [ ] **4.4.1** Criar `forexbot/strategies/strategy_c/strategy.py`

  ```python
  # forexbot/strategies/strategy_c/strategy.py
  """
  Estratégia C — Opening Range Breakout (ORB)

  Regras:
    Range: primeiros 30min da sessão London (07:00-07:30 UTC)
    LONG:  close > range_high + EMA50 aponta para cima
    SHORT: close < range_low  + EMA50 aponta para baixo

  SL:  1.5× ATR(14)
  TP:  2× SL (RR 1:2)
  TF:  M15 (só avalia às 07:15 e 07:30 UTC)
  """
  import pandas as pd
  import pandas_ta as ta
  import logging
  from datetime import timezone
  from forexbot.strategies.base import BaseStrategy
  from forexbot.core.candle import Candle
  from forexbot.core.signal import TradeSignal, Direction
  from forexbot.core import decision_logger as dl

  log = logging.getLogger(__name__)

  LONDON_RANGE_START_HOUR = 7
  LONDON_RANGE_START_MIN  = 0
  LONDON_RANGE_END_HOUR   = 7
  LONDON_RANGE_END_MIN    = 30

  class StrategyC(BaseStrategy):

      @property
      def name(self) -> str:
          return "C"

      def evaluate(self, symbol: str, candles: list[Candle]) -> TradeSignal | None:
          if len(candles) < 60:
              dl.log_no_signal("C", symbol, "candles insuficientes", {"count": len(candles)})
              return None

          last_candle = candles[-2]
          ts = last_candle.timestamp.astimezone(timezone.utc)

          # Só avaliar após o range (07:30+) e antes das 10:00 UTC
          if not (7 <= ts.hour < 10):
              dl.log_no_signal("C", symbol, f"fora da janela ORB (hora UTC={ts.hour})", {"hour": ts.hour})
              return None

          # Encontrar as velas do range 07:00-07:30 UTC
          range_candles = [
              c for c in candles
              if c.timestamp.astimezone(timezone.utc).hour == 7
              and c.timestamp.astimezone(timezone.utc).minute < 30
          ]

          if len(range_candles) < 2:
              dl.log_no_signal("C", symbol, "velas do range insuficientes", {"range_count": len(range_candles)})
              return None

          range_high = max(c.high for c in range_candles)
          range_low  = min(c.low  for c in range_candles)

          # EMA50 para filtro de tendência
          df = pd.DataFrame([{"close": c.close, "high": c.high, "low": c.low} for c in candles])
          df["ema50"] = ta.ema(df["close"], length=50)
          df["atr"]   = ta.atr(df["high"], df["low"], df["close"], length=14)
          curr = df.iloc[-2]

          ema50 = curr["ema50"]
          atr   = curr["atr"]
          close = last_candle.close

          indicators = {
              "range_high": round(range_high, 5),
              "range_low":  round(range_low, 5),
              "close":      round(close, 5),
              "ema50":      round(ema50, 5),
              "atr":        round(atr, 5),
          }

          # ── LONG: breakout acima do range + EMA50 aponta para cima
          if close > range_high and close > ema50:
              entry  = close
              sl     = entry - (1.5 * atr)
              tp     = entry + 2 * (entry - sl)
              reason = (f"ORB breakout ↑ | close={close:.5f} > range_high={range_high:.5f} "
                        f"· EMA50={ema50:.5f} (tendência ↑)")
              signal = TradeSignal("C", symbol, Direction.LONG, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          # ── SHORT: breakout abaixo do range + EMA50 aponta para baixo
          if close < range_low and close < ema50:
              entry  = close
              sl     = entry + (1.5 * atr)
              tp     = entry - 2 * (sl - entry)
              reason = (f"ORB breakout ↓ | close={close:.5f} < range_low={range_low:.5f} "
                        f"· EMA50={ema50:.5f} (tendência ↓)")
              signal = TradeSignal("C", symbol, Direction.SHORT, entry, sl, tp, reason, last_candle.timestamp)
              dl.log_signal(signal, indicators)
              return signal

          # Sem sinal
          if close > range_high:
              reason = f"Breakout ↑ mas close={close:.5f} < EMA50={ema50:.5f} (tendência não confirma)"
          elif close < range_low:
              reason = f"Breakout ↓ mas close={close:.5f} > EMA50={ema50:.5f} (tendência não confirma)"
          else:
              reason = f"Sem breakout | close={close:.5f} dentro de [{range_low:.5f}, {range_high:.5f}]"

          dl.log_no_signal("C", symbol, reason, indicators)
          return None
  ```

---

## FASE 5 — Loop principal e execução

### Etapa 5.1 — Risk Manager

- [ ] **5.1.1** Criar `forexbot/core/risk_manager.py`

  ```python
  # forexbot/core/risk_manager.py
  import logging
  from forexbot import config

  log = logging.getLogger(__name__)

  # Valor por pip por lote standard (aproximado para pares com USD como quote)
  # Para XAUUSD: 1 pip = $1 por 0.01 lot
  PIP_VALUE_PER_LOT = {
      "default": 10.0,   # $10 por pip por lot standard (maioria dos pares)
      "XAUUSD":  10.0,   # $10 por pip (1 pip = $0.10 × 100)
      "XAGUSD":  50.0,
      "BTCUSD":  1.0,
      "ETHUSD":  1.0,
      "SOLUSD":  1.0,
      "XRPUSD":  1.0,
  }

  MIN_LOT = 0.01
  MAX_LOT = 10.0

  def pip_value(symbol: str) -> float:
      return PIP_VALUE_PER_LOT.get(symbol, PIP_VALUE_PER_LOT["default"])

  def lot_size(equity: float, entry: float, sl: float, symbol: str) -> float:
      """
      Calcula o lote baseado em:
        - equity atual da conta
        - risco por trade (RISK_PCT do .env, default 1%)
        - distância ao SL em pips
      """
      risk_amount = equity * (config.RISK_PCT / 100)
      sl_pips     = abs(entry - sl) * 10000   # converter para pips (4 casas decimais)

      if sl_pips < 0.1:
          log.warning(f"SL demasiado pequeno ({sl_pips:.2f} pips) — a usar lote mínimo")
          return MIN_LOT

      lot = risk_amount / (sl_pips * pip_value(symbol))
      lot = round(max(MIN_LOT, min(MAX_LOT, lot)), 2)
      log.debug(f"lot_size: equity={equity} risk={risk_amount:.2f} sl_pips={sl_pips:.1f} lot={lot}")
      return lot
  ```

### Etapa 5.2 — Loop principal

- [ ] **5.2.1** Criar `forexbot/core/main_loop.py`

  ```python
  # forexbot/core/main_loop.py
  """
  Loop principal do bot.
  A cada fecho de vela M15, para cada par e estratégia ativa:
    1. Obter velas
    2. Avaliar estratégia
    3. Se sinal → calcular lote → abrir ordem
    4. Verificar posições abertas (fechar se TP/SL atingido)
  """
  import time
  import logging
  from datetime import datetime, timezone, timedelta
  from forexbot import config
  from forexbot.broker.ctrader_client import CTraderClient
  from forexbot.broker.ctrader_broker import CTraderBroker
  from forexbot.core.candle import Candle
  from forexbot.core import risk_manager
  from forexbot.core import decision_logger as dl
  from forexbot.strategies.strategy_a.strategy import StrategyA
  from forexbot.strategies.strategy_b.strategy import StrategyB
  from forexbot.strategies.strategy_c.strategy import StrategyC
  from forexbot.notifications.telegram import TelegramNotifier

  log = logging.getLogger(__name__)

  def bars_to_candles(bars: list) -> list[Candle]:
      """Converte barras cTrader em objetos Candle."""
      candles = []
      for b in bars:
          ts   = datetime.fromtimestamp(b.utcTimestampInMinutes * 60, tz=timezone.utc)
          low  = b.low / 100000
          candles.append(Candle(
              timestamp = ts,
              open  = low + b.open  / 100000,
              high  = low + b.high  / 100000,
              low   = low,
              close = low + b.close / 100000,
              volume= b.volume,
          ))
      return candles

  def next_m15_close() -> datetime:
      """Calcula o próximo fecho de vela M15."""
      now = datetime.now(timezone.utc)
      minutes = (now.minute // 15 + 1) * 15
      if minutes >= 60:
          return now.replace(minute=0, second=5, microsecond=0) + timedelta(hours=1)
      return now.replace(minute=minutes, second=5, microsecond=0)

  def run():
      log.info("🚀 ForexBot v2 a iniciar...")

      # Inicializar componentes
      tg      = TelegramNotifier()
      client  = CTraderClient(config.CTRADER_ACCESS_TOKEN)
      broker  = CTraderBroker(client)

      client.start()
      symbols_map = client.load_symbols()

      # Estratégias ativas
      strategies = []
      if config.STRATEGY_A_ENABLED:
          strategies.append(StrategyA())
      if config.STRATEGY_B_ENABLED:
          strategies.append(StrategyB())
      if config.STRATEGY_C_ENABLED:
          strategies.append(StrategyC())

      tg.send(
          f"✅ ForexBot v2 ligado\n"
          f"Pares: {len(config.SYMBOLS)}\n"
          f"Estratégias: {[s.name for s in strategies]}\n"
          f"DRY_RUN: {config.DRY_RUN}"
      )

      log.info(f"Estratégias: {[s.name for s in strategies]}")
      log.info(f"Pares: {config.SYMBOLS}")

      while True:
          # Aguardar próximo fecho M15
          target = next_m15_close()
          wait   = (target - datetime.now(timezone.utc)).total_seconds()
          if wait > 0:
              log.debug(f"Próximo ciclo em {wait:.0f}s ({target.strftime('%H:%M')} UTC)")
              time.sleep(wait)

          cycle_start = datetime.now(timezone.utc)
          log.info(f"── Ciclo M15 {cycle_start.strftime('%Y-%m-%d %H:%M')} UTC ──")

          equity = broker.get_equity()

          for symbol in config.SYMBOLS:
              for strategy in strategies:
                  try:
                      bars    = client.get_candles(symbol, "M15", count=200)
                      candles = bars_to_candles(bars)

                      if not candles:
                          dl.log_no_signal(strategy.name, symbol, "sem velas recebidas", {})
                          continue

                      signal = strategy.evaluate(symbol, candles)

                      if signal is not None:
                          lot = risk_manager.lot_size(equity, signal.entry, signal.sl, symbol)

                          if config.DRY_RUN:
                              ticket = f"dry-{signal.id}"
                              log.info(f"[DRY_RUN] {signal}")
                          else:
                              ticket = broker.open_trade(signal, lot)

                          dl.log_trade_open(signal, lot, ticket)
                          tg.send_signal(signal, lot, ticket)

                  except Exception as e:
                      log.error(f"Erro [{strategy.name}][{symbol}]: {e}", exc_info=True)

  if __name__ == "__main__":
      run()
  ```

---

## FASE 6 — Notificações Telegram

### Etapa 6.1 — Notificador Telegram

- [ ] **6.1.1** Criar bot no Telegram via @BotFather
  - Abrir Telegram → procurar @BotFather
  - Enviar `/newbot`
  - Nome: `ForexBot v2`
  - Username: `forexbotv2_bot` (ou similar disponível)
  - Copiar o token para o `.env` em `TELEGRAM_BOT_TOKEN`

- [ ] **6.1.2** Obter o Chat ID
  ```bash
  # Enviar qualquer mensagem ao bot e ir a:
  # https://api.telegram.org/bot<TOKEN>/getUpdates
  # O campo "chat.id" é o TELEGRAM_CHAT_ID
  ```

- [ ] **6.1.3** Criar `forexbot/notifications/telegram.py`

  ```python
  # forexbot/notifications/telegram.py
  import logging
  import requests
  from forexbot import config
  from forexbot.core.signal import TradeSignal, Direction

  log = logging.getLogger(__name__)

  class TelegramNotifier:

      def __init__(self):
          self._token   = config.TELEGRAM_BOT_TOKEN
          self._chat_id = config.TELEGRAM_CHAT_ID
          self._base    = f"https://api.telegram.org/bot{self._token}/sendMessage"

      def send(self, text: str):
          if not self._token or not self._chat_id:
              return
          try:
              requests.post(self._base, json={
                  "chat_id":    self._chat_id,
                  "text":       text,
                  "parse_mode": "HTML",
              }, timeout=10)
          except Exception as e:
              log.warning(f"Telegram erro: {e}")

      def send_signal(self, signal: TradeSignal, lot: float, ticket: str):
          emoji = "🟢" if signal.direction == Direction.LONG else "🔴"
          dry   = " [DRY RUN]" if config.DRY_RUN else ""
          msg = (
              f"{emoji} <b>OPEN TRADE{dry}</b> — Estratégia {signal.strategy}\n"
              f"Par: <b>{signal.symbol}</b> · {signal.direction.value}\n"
              f"Entrada: <code>{signal.entry:.5f}</code>\n"
              f"SL: <code>{signal.sl:.5f}</code> · TP: <code>{signal.tp:.5f}</code>\n"
              f"RR: <b>1:{signal.rr_ratio}</b> · Lot: <code>{lot}</code>\n"
              f"📋 {signal.reason}\n"
              f"🎫 Ticket: <code>{ticket}</code>"
          )
          self.send(msg)

      def send_close(self, ticket: str, symbol: str, strategy: str,
                     pnl: float, pips: float, exit_reason: str):
          emoji = "✅" if pnl >= 0 else "❌"
          msg = (
              f"{emoji} <b>CLOSE TRADE</b> — Estratégia {strategy}\n"
              f"Par: <b>{symbol}</b>\n"
              f"P&L: <code>{pnl:+.2f}$</code> ({pips:+.1f} pips)\n"
              f"Saída: {exit_reason}\n"
              f"🎫 Ticket: <code>{ticket}</code>"
          )
          self.send(msg)

      def send_daily_summary(self, stats: dict):
          msg = (
              f"📊 <b>Resumo Diário</b>\n"
              f"Trades: {stats.get('total', 0)}\n"
              f"Wins: {stats.get('wins', 0)} · Losses: {stats.get('losses', 0)}\n"
              f"P&L: <code>{stats.get('pnl', 0):+.2f}$</code>\n"
              f"Win rate: {stats.get('win_rate', 0):.1f}%"
          )
          self.send(msg)
  ```

---

## FASE 7 — Dashboard Web

### Etapa 7.1 — Configurar Django

- [ ] **7.1.1** Inicializar projeto Django
  ```bash
  django-admin startproject dashboard_project .
  python manage.py startapp dashboard
  ```

- [ ] **7.1.2** Adicionar modelos de dados em `dashboard/models.py`

  ```python
  # dashboard/models.py
  from django.db import models

  class Trade(models.Model):
      ticket    = models.CharField(max_length=50, unique=True)
      strategy  = models.CharField(max_length=5)   # A, B, C
      symbol    = models.CharField(max_length=20)
      direction = models.CharField(max_length=5)   # LONG, SHORT
      entry     = models.FloatField()
      sl        = models.FloatField()
      tp        = models.FloatField()
      lot       = models.FloatField()
      reason    = models.TextField()
      opened_at = models.DateTimeField()
      closed_at = models.DateTimeField(null=True, blank=True)
      pnl       = models.FloatField(null=True, blank=True)
      pips      = models.FloatField(null=True, blank=True)
      exit_reason = models.CharField(max_length=100, blank=True)

      class Meta:
          ordering = ["-opened_at"]

      def __str__(self):
          return f"{self.strategy} {self.symbol} {self.direction} {self.opened_at}"

  class DecisionLog(models.Model):
      ts        = models.DateTimeField()
      strategy  = models.CharField(max_length=5)
      symbol    = models.CharField(max_length=20)
      result    = models.CharField(max_length=20)  # SIGNAL, NO_SIGNAL
      reason    = models.TextField()
      indicators = models.JSONField(default=dict)

      class Meta:
          ordering = ["-ts"]
  ```

- [ ] **7.1.3** Criar migrações e base de dados
  ```bash
  python manage.py makemigrations dashboard
  python manage.py migrate
  ```

- [ ] **7.1.4** Criar views e templates básicos do dashboard
  - Página principal com: tabela de trades, gráfico de equity, filtro por estratégia
  - Página de logs: ver todas as decisões por par/estratégia/data

---

## FASE 8 — Commit e deploy

### Etapa 8.1 — Git

- [ ] **8.1.1** Primeiro commit com toda a estrutura
  ```bash
  git add .
  git commit -m "feat: estrutura base ForexBot v2 — 3 estratégias, multi-par, cTrader"
  git push origin main
  ```

- [ ] **8.1.2** Verificar no GitHub que o `.env` está presente (repo privado ✅)

### Etapa 8.2 — Teste final antes de ligar

- [ ] **8.2.1** Correr com `DRY_RUN=true` durante 24h e verificar:
  - Estão a aparecer logs em `logs/decisions/`?
  - O Telegram recebe mensagens?
  - O dashboard mostra as decisões?
  - Todos os pares estão a ser avaliados?

- [ ] **8.2.2** Mudar `DRY_RUN=false` no `.env` para começar a operar na conta demo real

---

---

## FASE 9 — Deploy final na VPS (quando o código estiver testado)

### Etapa 9.1 — Configurar systemd para o bot correr 24/7

- [ ] **9.1.1** Criar service do bot em `/etc/systemd/system/forexbot.service`
  ```bash
  sudo nano /etc/systemd/system/forexbot.service
  ```
  ```ini
  [Unit]
  Description=ForexBot v2 — Bot de trading automatizado
  After=network.target
  Wants=network-online.target

  [Service]
  Type=simple
  User=utilizador
  WorkingDirectory=/home/utilizador/ForexBotV2
  ExecStart=/home/utilizador/ForexBotV2/venv/bin/python run_bot.py
  Restart=always
  RestartSec=30
  StandardOutput=journal
  StandardError=journal

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] **9.1.2** Criar service do dashboard em `/etc/systemd/system/forexbot-dashboard.service`
  ```ini
  [Unit]
  Description=ForexBot v2 — Dashboard Django
  After=network.target

  [Service]
  Type=simple
  User=utilizador
  WorkingDirectory=/home/utilizador/ForexBotV2
  ExecStart=/home/utilizador/ForexBotV2/venv/bin/python run_dashboard.py
  Restart=always
  RestartSec=10
  StandardOutput=journal
  StandardError=journal

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] **9.1.3** Ativar e arrancar os serviços
  ```bash
  sudo systemctl daemon-reload
  sudo systemctl enable forexbot forexbot-dashboard
  sudo systemctl start forexbot forexbot-dashboard
  sudo systemctl status forexbot
  ```

### Etapa 9.2 — Ver logs na VPS

- [ ] **9.2.1** Comandos úteis para monitorizar o bot na VPS
  ```bash
  # Ver logs em tempo real do bot
  sudo journalctl -u forexbot -f

  # Ver últimas 100 linhas
  sudo journalctl -u forexbot -n 100

  # Ver decisões do dia de hoje
  tail -f /home/utilizador/ForexBotV2/logs/decisions/$(date +%Y-%m-%d).jsonl

  # Reiniciar o bot após alterar código
  sudo systemctl restart forexbot

  # Parar o bot temporariamente
  sudo systemctl stop forexbot
  ```

---

## Checklist de arranque rápido

**No Mac (dev — sem venv, sem pip):**
- [ ] Criar repo GitHub privado
- [ ] Clonar no Mac e criar estrutura de pastas
- [ ] Escrever todo o código (Fases 1-7)
- [ ] `git push` quando o código estiver pronto

**Na VPS Linux (runtime):**
- [ ] Configurar acesso SSH e git (Fase 0)
- [ ] `git clone` do repo privado
- [ ] `bash scripts/setup_vps.sh` (venv + pip install)
- [ ] Preencher `.env` com Client ID, Secret, Account ID, Telegram token
- [ ] `python -m forexbot.broker.ctrader_auth` (autenticação OAuth — **ponto mínimo de teste**)
- [ ] `python scripts/connect_check.py` ✅ → **app pode ser testada a partir daqui**
- [ ] `python run_bot.py` (com DRY_RUN=true)
- [ ] Verificar Telegram a receber mensagens
- [ ] Verificar logs em `logs/decisions/`
- [ ] Configurar systemd para correr 24/7 (Fase 9)

---

> **Lembra-te:** começar sempre com `DRY_RUN=true`.
> Só mudar para `false` depois de confirmar que tudo está a funcionar corretamente.
