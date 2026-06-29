# ForexBot v2

Bot de trading automatizado · cTrader Open API · Python · Django · Telegram

## Ambientes

| O que | Onde |
|---|---|
| Escrever código, `git push` | Mac (dev) |
| Instalar dependências, correr bot, dashboard | **VPS Linux** |

A biblioteca `ctrader-open-api` usa Twisted com TCP nativo e **não funciona no Mac**.
Todo o runtime acontece na VPS.

## Setup na VPS (Linux)

```bash
git clone git@github.com:BrunoKorpuzCoelho/new_forexbots.git
cd new_forexbots
bash scripts/setup_vps.sh
cp .env.example .env   # preencher credenciais
source venv/bin/activate
python forexbot/config.py
```

## Fluxo de trabalho

```
Mac (dev)                    VPS Linux (runtime)
─────────                    ───────────────────
Editar código          →
git push               →     git pull
                       →     python run_bot.py
Ver dashboard          ←     http://IP_DA_VPS:8000
```

## Estrutura

Ver [`TASKS.md`](TASKS.md) para o plano completo de desenvolvimento.
