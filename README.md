# Meeting Room Monitor

Aplicação Python que monitora as agendas das salas de conferência da organização, integrando com a **Microsoft Graph API** e abrindo chamados automaticamente no **InvGate Service Desk**.

## Visão Geral

O sistema consulta automaticamente o calendário de cada sala de reunião registrada no Microsoft 365, filtra os eventos com base em regras de negócio e, quando uma reunião válida é detectada, abre um chamado de ronda diária no InvGate.

O ciclo de verificação é executado a cada **5 minutos** de forma contínua.

## Funcionalidades

- Autenticação automática com renovação de token via MSAL (Microsoft Graph)
- Autenticação Basic Auth no InvGate ITSM
- Busca de salas de reunião diretamente do Microsoft 365 (sem configuração manual)
- Consulta de eventos do dia corrente (00:00 às 23:59) para cada sala
- Filtragem de reuniões por regras de negócio (canceladas, dia inteiro, status, etc.)
- Cálculo de horário de vistoria (15 minutos antes do início)
- Abertura automática de chamados no InvGate ao detectar reunião válida
- Controle de duplicidade por sala/dia via `.daily_tickets.json`
- Tratamento de rate limiting (HTTP 429) com retry automático
- Paginação automática de resultados da Graph API
- Dashboard web com visualização em cards e calendário

## Estrutura do Projeto

```
.
├── app.py                  # Ponto de entrada — loop principal
├── dashboard.py            # Servidor Flask do dashboard web
├── requirements.txt
├── get_token.py            # Utilitário para verificar credenciais InvGate
├── config/
│   ├── config.py           # Credenciais Microsoft (variáveis de ambiente)
│   └── rooms.py            # Carrega salas dinamicamente via Graph API
├── core/
│   ├── auth.py             # Autenticação MSAL (Client Credentials)
│   └── graph.py            # Cliente HTTP para Microsoft Graph API
├── dashboard/
│   ├── static/style.css    # Estilos do dashboard
│   └── templates/index.html
├── rules/
│   └── rules.py            # Regras de validação de eventos
├── services/
│   ├── calendar.py         # Serviço de consulta de calendário
│   └── invgate.py          # Integração com InvGate ITSM
└── utils/
    ├── daily_control.py    # Controle local de chamados abertos por dia
    └── time_utils.py       # Utilitários de data/hora (fuso America/Sao_Paulo)
```

## Pré-requisitos

- Python 3.9+
- App Registration no Azure AD com permissões de aplicativo:
  - `Calendars.Read`
  - `Place.Read.All`
- Credencial Basic Auth no InvGate (tipo "Básico" no painel de integrações)

## Instalação

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd <nome-do-projeto>

# Crie e ative um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Instale as dependências
pip install -r requirements.txt
```

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
# Microsoft Graph (Azure AD)
CLIENT_ID=seu-client-id
CLIENT_SECRET=seu-client-secret
TENANT_ID=seu-tenant-id

# InvGate ITSM
INVGATE_ENV=staging

INVGATE_USERNAME=seu-usuario-invgate
INVGATE_API_KEY=sua-chave-invgate

# URL de produção (staging já está configurado no serviço)
INVGATE_PROD_URL=https://sua-empresa.sd.cloud.invgate.net

# IDs do InvGate
INVGATE_CUSTOMER_ID=0
INVGATE_CREATOR_ID=0
INVGATE_CATEGORY_ID=0
INVGATE_PRIORITY_ID=2
INVGATE_TYPE_ID=2
```

> Nunca versione o `.env`. Ele já está no `.gitignore`.

## Uso

Monitor contínuo (abre chamados automaticamente):

```bash
python app.py
```

Dashboard web:

```bash
python dashboard.py
# Acesse http://localhost:5000
```

O dashboard expõe os seguintes endpoints:

| Endpoint             | Descrição                                              |
|----------------------|--------------------------------------------------------|
| `GET /`              | Interface web do dashboard                             |
| `GET /api/rooms`     | Lista salas com reuniões do dia e status em tempo real |
| `GET /api/calendar`  | Eventos formatados para o calendário (FullCalendar)    |
| `GET /api/rooms/status` | Status de acesso de cada sala via Graph API         |

Exemplo de saída do monitor:

```
🔎 Iniciando verificação de reuniões...

📡 Verificando agenda: sala.a@empresa.com
   📅 Reunião agendada encontrada!
   📌 Título: Alinhamento de Sprint
   📍 Sala:   Sala A
   ⏰ Início: 07/04/2026 14:00
   ⏳ Fim:    07/04/2026 15:00
   🛠️ Vistoria: 07/04/2026 13:45
   🎫 Chamado InvGate criado: #4614 — open
   ✅ Pronto para ação
```

## Regras de Validação de Eventos

Um evento é considerado válido quando:

- Não está cancelado (`isCancelled = false`)
- Não é um evento de dia inteiro (`isAllDay = false`)
- O status é `busy` ou `oof`
- Possui localização (sala) definida (`location.displayName` preenchido)
- O título não contém termos bloqueados: `chamando`, `evento automático`, `recorrência`

## Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| Sala com mailbox inativa / on-premise (erro 404) | Retry interrompido imediatamente; sala ignorada |
| Rate limiting HTTP 429 | Aguarda o tempo indicado no cabeçalho `Retry-After` |
| Falha na criação do chamado no InvGate | Erro registrado no terminal; nova tentativa no próximo ciclo (5 min) |
| Chamado já aberto para a sala no dia | Processamento encerrado para a sala; nenhuma ação executada |
