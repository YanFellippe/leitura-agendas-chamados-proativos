Contrato: Advocacia-Geral da União

Elaborador: André Nascimento

Nível de Sigilo: Não Sigiloso

Disciplina: Requisição de Serviço

Data de publicação: NÃO PUBLICADO

Grupo executor: Automações

Serviço: A DEFINIR

Aprovador/Revisor: ednilta.santos

Atividade: Serviço: A DEFINIR

---

# DOCUMENTO DE AUTOMAÇÃO — Leitura de Agendas e Chamados Proativos

---

## Proposta de Automação

**Data:** 20/08/2026
**Responsável:** Yan Basílio
**Área/Sistema:** Monitoramento / Microsoft Graph API / InvGate ITSM

---

## 1. Objetivo

**Problema resolvido:**
As salas de reunião da AGU necessitam de vistoria técnica preventiva (verificação de equipamentos audiovisuais e conectividade) antes do início de reuniões agendadas. Esse processo era realizado manualmente, dependendo de um operador para verificar as agendas e abrir chamados de vistoria no InvGate ITSM.

**Atividade automatizada:**
A automação lê as agendas corporativas de 88 salas de reunião via Microsoft Graph API, identifica reuniões válidas e abre automaticamente chamados de vistoria no InvGate ITSM com antecedência, sem intervenção humana.

**Ganhos esperados:**

- Eliminação da verificação manual de agendas
- Redução de falhas humanas (reuniões sem vistoria)
- Garantia de vistoria preventiva para todas as reuniões válidas
- Visibilidade em tempo real do status das salas via dashboard web
- Abertura antecipada de chamados para reuniões que ocorrem nas primeiras horas do dia seguinte

---

## 2. Escopo

### O que a automação FAZ:

- Consulta as agendas de 87 salas de reunião cadastradas via Microsoft Graph API
- Valida se a reunião atende aos critérios de negócio (não cancelada, não o dia inteiro, status "busy" ou "oof", com local definido)
- Abre chamados de vistoria no InvGate ITSM automaticamente
- Controla duplicidade: apenas um chamado por sala por dia
- Verifica reuniões do dia seguinte que começam até às 9h e abre chamados antecipados
- Disponibiliza dashboard web com visualização em tempo real (cards, calendário, status, histórico)
- Permite abertura manual de chamados via dashboard (botão "Abrir Vistoria")
- Registra histórico de chamados abertos em arquivo JSON local

### O que a automação NÃO FAZ:

- Não realiza a vistoria física nas salas
- Não envia notificações por email ou Teams
- Não gerencia o ciclo de vida do chamado no InvGate (acompanhamento, fechamento)
- Não cria ou modifica reuniões no calendário
- Não gerencia permissões de acesso às salas
- Não faz integração com sistemas de controle de acesso físico

---

## 3. Descrição do Fluxo

### Fluxo Principal (Abertura Automática de Chamados)

1. **Gatilho:** Ciclo automático a cada 5 minutos (300 segundos)
2. **Entrada de dados:** Lista de 88 emails de salas de reunião monitoradas
3. **Processamento:**
   - Para cada sala, consulta a Microsoft Graph API (`/users/{email}/calendarView`) para obter eventos do dia
   - Aplica regras de validação em cada evento encontrado
   - Verifica no controle local (`.daily_tickets.json`) se já foi aberto chamado para a sala hoje
4. **Ação executada:** Se a reunião é válida e não há chamado aberto, cria chamado no InvGate ITSM via API REST (`POST /api/v1/incident`)
5. **Saída:** Chamado criado com ID registrado no controle local; log no console

### Fluxo Secundário (Chamados Antecipados)

1. **Gatilho:** Executado ao final de cada ciclo principal
2. **Entrada:** Reuniões do dia seguinte que começam até às 9h
3. **Processamento:** Mesmas validações do fluxo principal
4. **Ação:** Abre chamado antecipado com marcação especial no controle local
5. **Saída:** Chamado criado com flag `anticipated=true`

### Fluxo Dashboard (Visualização e Ação Manual)

1. **Gatilho:** Acesso via navegador na porta 5000
2. **Abas disponíveis:**
   - **Cards:** Visualização em tempo real das salas e reuniões do dia
   - **Calendário:** Visão mensal/semanal/diária dos eventos (FullCalendar)
   - **Status:** Verificação de acessibilidade de cada sala na Graph API
   - **Histórico:** Registro de chamados abertos com filtro por período
3. **Ação manual:** Botão "Abrir Vistoria" permite forçar abertura de chamado para qualquer sala

---

## 4. Regras de Negócio

### Critérios para uma reunião ser considerada válida:

- Evento **não cancelado** (`isCancelled = false`)
- Evento **não é dia inteiro** (`isAllDay = false`)
- Status do evento é **"busy"** ou **"oof"** (fora do escritório)
- Evento possui **local (displayName) preenchido**
- Título do evento **não contém** palavras bloqueadas: "chamando", "evento automático", "recorrência"

### Regras de controle de duplicidade:

- Apenas **1 chamado automático por sala por dia**
- Chamados forçados (via dashboard) são sempre permitidos e registrados com flag `forced=true`
- Chamados antecipados usam chave composta: `{sala}|antecipado|{data_reuniao}`

### Regras de concorrência (Microsoft Graph API):

- Máximo de 2 workers simultâneos
- Processamento em lotes de 10 salas com pausa de 0.5s entre lotes
- Retry automático (até 3 tentativas com backoff de 2/4/6 segundos) em caso de erro `MailboxConcurrency`
- Rate limiting respeitado via header `Retry-After` (HTTP 429)

### Regras do chamado InvGate:

- Criador e solicitante (customer): ticketbot (ID 20868)
- Categoria: conforme `INVGATE_CATEGORY_ID` (3092 — Ronda diária)
- Prioridade: Medium (ID 2)
- Tipo: Service Request (ID 2)
- Título segue o padrão: `Validação Proativa de Sala de Reunião – {Local} – {DD/MM/YYYY HH:MM}`

---

## 5. Requisitos Técnicos

### Linguagem:

- Python 3.11+

### Bibliotecas/Dependências:

- `flask` — servidor web do dashboard
- `requests` — requisições HTTP (Graph API e InvGate)
- `msal` — autenticação OAuth2 com Microsoft Identity Platform
- `python-dotenv` — carregamento de variáveis de ambiente
- `pytz` / `zoneinfo` — manipulação de fusos horários

### APIs envolvidas:

| API                      | Uso                                                                                                         |
| ------------------------ | ----------------------------------------------------------------------------------------------------------- |
| Microsoft Graph API v1.0 | Leitura de agendas (`/users/{email}/calendarView`) e listagem de salas (`/places/microsoft.graph.room`) |
| InvGate ITSM API v1      | Criação de chamados (`POST /api/v1/incident`) e busca de usuários (`/api/v1/users.by`)               |

### Autenticação:

- **Microsoft Graph:** OAuth2 Client Credentials (app-only) via MSAL
- **InvGate:** HTTP Basic Auth (username + API key)

### Infraestrutura:

- Execução local ou em servidor Windows
- Porta 5000 (dashboard Flask)
- Acesso à internet para APIs externas

### Arquivos utilizados:

| Arquivo                             | Função                                                    |
| ----------------------------------- | ----------------------------------------------------------- |
| `.env`                            | Variáveis de ambiente (credenciais, IDs de configuração) |
| `.daily_tickets.json`             | Controle local de chamados abertos por dia                  |
| `config/whitelist/whitelist.json` | Mapeamento de salas com tag_name e local para o InvGate     |

### Estrutura do projeto:

```
├── app.py                    # Loop principal de monitoramento
├── dashboard.py              # Servidor Flask (dashboard web)
├── config/
│   ├── config.py             # Carrega variáveis de ambiente
│   ├── rooms.py              # Carregamento e cache de salas
│   ├── whitelist.py          # Lookup de tag/local por email
│   └── whitelist/
│       └── whitelist.json    # Dados das salas (tag, local, email)
├── core/
│   ├── auth.py               # Autenticação Microsoft (MSAL)
│   └── graph.py              # Cliente HTTP para Graph API
├── services/
│   ├── calendar.py           # Busca de eventos (Graph API)
│   └── invgate.py            # Criação de chamados (InvGate API)
├── rules/
│   └── rules.py              # Regras de validação de reuniões
├── utils/
│   ├── daily_control.py      # Controle de duplicidade por dia
│   └── time_utils.py         # Utilitários de data/hora
├── dashboard/
│   ├── templates/
│   │   └── index.html        # Interface web do dashboard
│   └── static/
│       └── style.css         # Estilos do dashboard
├── requirements.txt          # Dependências Python
└── .env                      # Configuração (não versionado)
```

---

## 6. Tratamento de Erros

### Microsoft Graph API:

- **HTTP 429 (Rate Limit):** Aguarda o tempo indicado no header `Retry-After` e retenta
- **HTTP 404 (Mailbox não encontrada):** Ignora a sala sem retry (mailbox inativa ou on-premise)
- **MailboxConcurrency limit:** Retry automático com backoff progressivo (2s, 4s, 6s) — até 3 tentativas
- **Erro genérico:** Retry até 3 vezes com intervalo de 2 segundos

### InvGate API:

- **Falha na criação do chamado:** Exceção capturada, sala marcada como processada (evita loop infinito), erro logado no console
- **Timeout:** Configurado em 30 segundos por requisição

### Registro de erros:

- Todos os erros são logados no console (stdout) com prefixo indicativo (`⚠️`)
- O controle de duplicidade garante que uma falha não cause reprocessamento infinito

### Comportamento em caso de falha geral:

- O ciclo continua processando as demais salas
- Na próxima execução (5 minutos), as salas que falharam são verificadas novamente

---

## 7. Monitoramento

### Como saber se está funcionando:

- O dashboard web (porta 5000) exibe os dados em tempo real
- A aba "Histórico" mostra chamados abertos com data, sala e status
- A aba "Status das Salas" verifica se cada sala está acessível na Graph API
- O console exibe logs detalhados de cada ciclo de execução

### Logs disponíveis:

- Console (stdout): logs com emojis indicativos para cada etapa
  - `📡` Verificação de agenda
  - `📅` Reunião encontrada
  - `🎫` Chamado criado
  - `⏭️` Chamado já existente (skip)
  - `⚠️` Erros
  - `⏱️` Tempo total do ciclo

### Métricas relevantes:

- Número de salas monitoradas (87)
- Chamados abertos por dia (visível no histórico)
- Tempo de execução por ciclo (logado ao final)
- Taxa de erros de concorrência (visível nos logs)

---

## 8. Riscos

### Pontos de falha conhecidos:

| Risco                                      | Impacto                    | Mitigação                                                    |
| ------------------------------------------ | -------------------------- | -------------------------------------------------------------- |
| Token Microsoft expirado                   | Nenhuma agenda é lida     | MSAL gerencia refresh automático via `acquire_token_silent` |
| InvGate indisponível                      | Chamados não são criados | Retry na próxima execução (5 min)                           |
| MailboxConcurrency limit                   | Algumas salas sem dados    | Retry com backoff + processamento em lotes                     |
| Arquivo `.daily_tickets.json` corrompido | Duplicidade de chamados    | Lock thread-safe + formato JSON simples                        |
| Credenciais expiradas no `.env`          | Autenticação falha       | Monitoramento via logs e aba Status                            |

### Dependências críticas:

- Microsoft Graph API (disponibilidade e limites de throttling)
- InvGate ITSM API (disponibilidade)
- Rede/Internet (acesso às APIs externas)
- Credenciais válidas (Client Secret do Azure AD, API Key do InvGate)

### Impactos em caso de erro:

- **Sem impacto destrutivo:** a automação apenas cria chamados, não modifica dados existentes
- **Pior cenário:** chamados não são abertos, vistoria não é realizada preventivamente (retorno ao processo manual)

---

## 9. Critérios de Sucesso

| Indicador                     | Meta                                                  |
| ----------------------------- | ----------------------------------------------------- |
| Tempo de execução por ciclo | < 60 segundos para 87 salas                           |
| Chamados criados corretamente | 100% das reuniões válidas geram chamado             |
| Taxa de duplicidade           | 0% (controle por arquivo local)                       |
| Disponibilidade do dashboard  | Acessível continuamente na porta 5000                |
| Redução de esforço manual  | Eliminação total da verificação manual de agendas |
| Taxa de erro aceitável       | < 5% de falhas transitórias por ciclo                |

---

## 10. Evidências e Testes

### Validação funcional:

- Execução em ambiente staging do InvGate (`agu-staging.sd.cloud.invgate.net`)
- Verificação de chamados criados na interface do InvGate
- Conferência do título, descrição e campos do chamado
- Teste de duplicidade (executar ciclo duas vezes e confirmar que não duplica)

### Tipos de teste:

| Tipo               | Descrição                                            |
| ------------------ | ------------------------------------------------------ |
| Integrado          | Execução completa contra Graph API e InvGate staging |
| Manual (dashboard) | Abertura de chamado via botão "Abrir Vistoria"        |
| Concorrência      | Validação do comportamento com 87 salas simultâneas |
| Resiliência       | Simulação de timeout e erro 429 para verificar retry |

### Exemplo de entrada e saída:

**Entrada (evento da Graph API):**

```json
{
  "subject": "Reunião de alinhamento DTI",
  "start": {"dateTime": "2026-08-20T14:00:00", "timeZone": "E. South America Standard Time"},
  "end": {"dateTime": "2026-08-20T15:00:00", "timeZone": "E. South America Standard Time"},
  "location": {"displayName": "Sala de Reunião DTI"},
  "showAs": "busy",
  "isCancelled": false,
  "isAllDay": false,
  "organizer": {"emailAddress": {"address": "usuario@agu.gov.br", "name": "Usuário"}}
}
```

**Saída (chamado no InvGate):**

```json
{
  "request_id": 12345,
  "status": "success"
}
```

---

## 11. Plano de Implantação

### Onde será implantado:

- Servidor Windows com Python 3.11+ instalado
- Acesso à internet para APIs Microsoft e InvGate

### Passos de deploy:

1. Clonar o repositório: `git clone <url_repositorio>`
2. Instalar dependências: `pip install -r requirements.txt`
3. Configurar o arquivo `.env` com as credenciais:
   - `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` (Azure AD)
   - `INVGATE_USERNAME`, `INVGATE_API_KEY` (InvGate)
   - `INVGATE_CREATOR_ID=20868` (ticketbot)
   - `INVGATE_CATEGORY_ID`, `INVGATE_PRIORITY_ID`, `INVGATE_TYPE_ID`
   - `INVGATE_ENV=staging` ou `production`
4. Executar: `python dashboard.py` (inicia dashboard + loop de monitoramento)
5. Acessar o dashboard: `http://localhost:5000`

### Dependências para ativação:

- Registro de aplicação no Azure AD com permissões Graph API (Calendars.Read, Place.Read.All)
- Conta de API no InvGate com permissão de criação de chamados
- Usuário ticketbot (ID 20868) cadastrado no InvGate

---

## 12. Plano de Rollback

### Como desativar a automação:

- Encerrar o processo Python (`Ctrl+C` ou kill do processo)
- O dashboard e o loop de monitoramento param imediatamente
- Nenhum chamado será mais aberto automaticamente

### Como voltar ao processo manual:

- Operadores voltam a verificar agendas manualmente no Outlook/Teams
- Chamados de vistoria são abertos manualmente no InvGate

### Impactos da reversão:

- Reuniões podem ocorrer sem vistoria preventiva
- Aumento de carga operacional na equipe de suporte
- Perda de visibilidade centralizada (dashboard)
- O arquivo `.daily_tickets.json` permanece intacto como histórico

---

## 13. Observações Gerais

### Melhorias futuras:

- Migração para ambiente `production` do InvGate (atualmente em staging)
- Notificações por Teams/Email quando chamado é criado
- Dashboard com autenticação (login SSO)
- Persistência em banco de dados em vez de arquivo JSON local
- Configuração das salas monitoradas via interface administrativa
- Métricas e alertas via Zabbix/Grafana

### Limitações conhecidas:

- A lista de salas monitoradas é fixa no código (`dashboard.py`); alterações requerem deploy
- O controle de duplicidade depende do arquivo local `.daily_tickets.json` — se removido, pode gerar chamados duplicados no mesmo dia
- Salas com mailbox on-premise ou inativas no Microsoft 365 retornam erro 404 e são ignoradas
- O limite de concorrência da Microsoft Graph pode causar lentidão em horários de pico

### Ajustes planejados:

- Definir o campo `local` na whitelist para todas as 87 salas (atualmente apenas algumas possuem)
- Avaliar aumento do `batch_size` conforme comportamento em produção
- Configurar variável `INVGATE_ENV=production` quando ambiente estiver homologado
