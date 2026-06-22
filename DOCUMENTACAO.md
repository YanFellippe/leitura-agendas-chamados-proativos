# Documentação Técnica — Automação de Chamados Proativos para Salas de Reunião

---

## 1. Objetivo

Identificou-se que o processo atual de abertura de chamados para vistoria de salas de reunião ocorre de forma recorrente e indiscriminada, exigindo que um Técnico de Experiência do Cliente N2 realize inspeções diárias em todas as salas. Entretanto, nem todas as salas possuem reuniões agendadas diariamente, o que torna a execução dessa atividade, em diversos casos, desnecessária. Atualmente, esses chamados são previamente programados na plataforma InvGate.

Para mitigar essa ineficiência, foi implementado um mecanismo de automação responsável pela geração de chamados de forma dinâmica no InvGate, considerando a agenda específica de cada sala, conforme os agendamentos registrados na plataforma Outlook. Dessa forma, as vistorias passarão a ser realizadas exclusivamente nos dias em que houver reuniões programadas, eliminando a necessidade de abertura diária de chamados sem demanda efetiva.

Estima-se que um Técnico N2 despenda, em média, entre 45 (quarenta e cinco) minutos e 1 (uma) hora para a realização de cada vistoria. Com a implementação da automação proposta, esse tempo poderá ser otimizado e redirecionado para a execução de outras atividades de suporte ou demandas correlatas, aumentando a eficiência operacional da equipe.

---

## 2. Escopo

A automação realiza a verificação das agendas das salas de reunião por meio da integração com a plataforma Outlook e, com base nessas informações, efetua a abertura proativa de chamados direcionados aos Técnicos de Experiência do Cliente N2.

As conexões com as agendas das salas de reunião são realizadas por meio de requisições à API denominada "Leitura Agendas Outlook - Chamados Proativos". Atualmente, a identificação das salas está condicionada ao seu cadastro e status ativo no sistema. Encontra-se em andamento a evolução do mecanismo de consulta, com o objetivo de ampliar a abrangência da busca e possibilitar a detecção de salas que, até o momento, não estão devidamente cadastradas ou visíveis na aplicação.

---

## 3. Descrição do Fluxo

### Evento inicial (gatilho)

A execução do script `app.py` ocorre de forma manual ou por meio de agendamento via Task Scheduler. O processo é iniciado em ciclos recorrentes a cada 5 (cinco) minutos, realizando a verificação de todas as salas de reunião monitoradas.

### Entrada de dados

- Lista de salas de reunião obtida dinamicamente por meio da API Microsoft Graph, utilizando o recurso `microsoft.graph.room`;
- Eventos de calendário associados a cada sala, considerando o dia corrente completo (00:00 às 23:59, horário de Brasília), obtidos via endpoint `/users/{email}/calendarView`.

### Processamentos/validações

Aplicação de regras de negócio para filtragem dos eventos, desconsiderando:

- Reuniões canceladas;
- Eventos de dia inteiro (all-day);
- Eventos com status diferente de `busy` ou `out of office (oof)`;
- Eventos sem localização definida;
- Eventos cujo título contenha termos previamente bloqueados.

Verificação de controle local por meio do arquivo `.daily_tickets.json`, com o objetivo de identificar se já existe chamado registrado para a sala na data corrente. Caso seja identificado registro prévio para a sala no dia vigente, o processamento é encerrado para a respectiva sala, sem execução de novas ações.

### Ações executadas

Para a primeira reunião válida identificada em cada sala, é realizada uma requisição HTTP do tipo POST ao endpoint `/api/v1/incident` da API do InvGate, utilizando autenticação do tipo Basic Authentication. Após a criação bem-sucedida do chamado, a sala é registrada no controle local, juntamente com a data de processamento, garantindo rastreabilidade e controle de duplicidade.

### Saídas geradas

- Criação de chamado de ronda diária na plataforma InvGate, com o seguinte padrão de título: `"Ronda diária - {nome da sala}"`, contendo:
  - Identificação da sala;
  - Título da reunião;
  - Horário de início do evento.
- Registro em log no terminal, contendo:
  - Identificador do chamado criado (ex: `#ID`), ou
  - Informação de que já existe chamado previamente registrado para a sala na data corrente.
- Persistência de dados no arquivo `.daily_tickets.json`, utilizado como mecanismo de controle para evitar duplicidade de chamados ao longo das execuções no mesmo dia.

---

## 4. Regras de Negócio

### Critérios de Execução

Para que um chamado seja automaticamente aberto, o evento de calendário deve atender, simultaneamente, a todas as condições abaixo:

- O status do evento deve ser `busy` ou `out of office (oof)`, sendo desconsiderados eventos com status `free`, `tentative` ou `workingElsewhere`;
- O evento não deve estar marcado como cancelado (`isCancelled = false`);
- O evento não deve ser classificado como evento de dia inteiro (`isAllDay = false`);
- O evento deve possuir localização definida (`location.displayName` preenchido);
- O título do evento não deve conter termos bloqueados, tais como: `"chamando"`, `"evento automático"` ou `"recorrência"`.

O chamado é criado utilizando parâmetros fixos, previamente configurados por meio de variáveis de ambiente (`.env`), conforme descrito a seguir:

- Tipo: Service Request (`type_id = 2`);
- Prioridade: Média (`priority_id = 2`);
- Categoria: Ronda diária (`category_id` configurável);
- Criador e Cliente: Usuário de serviço definido nas variáveis `INVGATE_CREATOR_ID` e `INVGATE_CUSTOMER_ID`.

### Regras de Bloqueio

**Controle de duplicidade por sala/dia:** É permitida a abertura de apenas um chamado por sala a cada dia corrente. O controle é realizado localmente por meio do arquivo `.daily_tickets.json`. Caso a sala já esteja registrada para a data vigente, nenhuma nova ação será executada, independentemente da quantidade de reuniões existentes.

**Salas com erro de acesso:** Salas que apresentarem erro HTTP 404 (mailbox inativa ou ambiente on-premise) têm o retry interrompido imediatamente, sem geração de chamado.

**Ausência de eventos válidos:** Caso não sejam identificados eventos que atendam aos critérios estabelecidos após a aplicação das regras de validação, nenhum chamado será gerado para a sala.

### Condições Obrigatórias para Funcionamento

Para o correto funcionamento da automação, as seguintes condições devem ser integralmente atendidas:

**Configuração de variáveis de ambiente:** Devem estar devidamente configuradas as seguintes variáveis:
- `CLIENT_ID`, `CLIENT_SECRET`, `TENANT_ID` (integração com Microsoft Graph);
- `INVGATE_USERNAME`, `INVGATE_API_KEY`, `INVGATE_CUSTOMER_ID`, `INVGATE_CREATOR_ID`, `INVGATE_CATEGORY_ID`.

**Permissões no Azure AD:** O registro da aplicação (App Registration) deve possuir, no mínimo, as seguintes permissões de aplicativo (Application):
- `Calendars.Read`;
- `Place.Read.All`.

**Permissões na API do InvGate:** A credencial utilizada via Basic Authentication deve possuir permissão para criação de chamados, especificamente para o recurso `api/v1/incident` (método POST).

**Validação de identificadores no InvGate:** Os identificadores configurados no arquivo `.env` (`customer_id`, `creator_id` e `category_id`) devem existir e ser válidos no ambiente de destino (ex.: `staging` ou `production`).

**Permissão de escrita em arquivo local:** O arquivo `.daily_tickets.json` deve possuir permissão de escrita no diretório raiz do projeto, garantindo o correto funcionamento do mecanismo de controle de duplicidade.

---

## 5. Requisitos Técnicos

**Linguagem utilizada:** Python 3.9 ou superior

**Bibliotecas ou dependências:**

| Biblioteca | Finalidade |
|---|---|
| `requests` | Requisições HTTP para as APIs do Microsoft Graph e InvGate |
| `msal` | Autenticação OAuth2 Client Credentials com o Azure AD |
| `python-dotenv` | Leitura das variáveis de ambiente do arquivo `.env` |
| `zoneinfo` | Conversão de fusos horários (UTC → America/Sao_Paulo) |
| `flask` | Servidor web do dashboard de monitoramento |

### APIs envolvidas

**Microsoft Graph API:**
- Endpoint base: `https://graph.microsoft.com/v1.0`
- Autenticação: OAuth 2.0, fluxo Client Credentials via Azure Active Directory (Azure AD)
- Permissões necessárias (tipo Aplicativo):
  - `Calendars.Read`
  - `Place.Read.All`
- Recursos e endpoints utilizados:
  - `/places/microsoft.graph.room` — obtenção da lista de salas de reunião
  - `/users/{email}/calendarView` — consulta de eventos de calendário por sala

**InvGate Service Management API:**
- Endpoint base: `https://agu-staging.sd.cloud.invgate.net/api/v1/`
- Autenticação: Basic Authentication (username + API Key)
- Endpoints utilizados:
  - `POST /incident` — criação de chamados
  - `GET /categories` — consulta de categorias disponíveis
  - `GET /users` — consulta de usuários cadastrados

### Infraestrutura

A aplicação pode ser executada em qualquer servidor ou estação de trabalho que possua o ambiente Python na versão 3.9 ou superior, bem como acesso à internet para comunicação com as APIs externas. Não há necessidade de banco de dados ou infraestrutura dedicada, uma vez que o controle de estado é realizado localmente por meio de arquivos.

Para execução contínua em ambiente de produção, recomenda-se:
- `systemd` ou `cron`, em sistemas operacionais Linux;
- Task Scheduler, em sistemas operacionais Windows.

### Arquivos utilizados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `.env` | Variáveis de ambiente | Armazena credenciais e parâmetros de configuração sensíveis da aplicação |
| `.daily_tickets.json` | JSON | Controle local de chamados abertos por sala e por dia |
| `requirements.txt` | Texto | Lista de dependências necessárias para execução do projeto em Python |

---

## 6. Tratamento de Erros

### O que acontece em caso de falha

| Cenário | Comportamento do Sistema |
|---|---|
| Sala com mailbox inativa ou ambiente on-premise (erro HTTP 404) | Retry interrompido imediatamente; sala desconsiderada e processamento segue para a próxima |
| Falha na autenticação com o Azure AD | Exceção lançada com registro de erro no terminal; ciclo de execução interrompido |
| Falha na criação de chamado no InvGate (HTTP 4xx ou 5xx) | Erro capturado e registrado no terminal; sala não registrada no controle local, permitindo nova tentativa no próximo ciclo |
| Sala sem eventos válidos após filtragem | Nenhuma ação executada; registrado apenas log informativo no terminal |
| Variáveis de ambiente ausentes ou inválidas | Erro em tempo de execução ao utilizar valores nulos (`None`) nas requisições às APIs |

### Política de retry

**Microsoft Graph API:** Até 3 (três) tentativas por requisição, com intervalo de 2 (dois) segundos entre cada tentativa. Em casos de rate limiting (HTTP 429), o sistema aguarda o tempo indicado no cabeçalho `Retry-After` antes de nova tentativa. Erros HTTP 404 interrompem o retry imediatamente.

**InvGate API:** Não há retry automático. Em caso de falha, uma nova tentativa ocorre automaticamente no próximo ciclo de execução (intervalo padrão de 5 minutos).

### Como o erro é registrado

Atualmente, todos os erros são registrados exclusivamente no terminal (stdout), sem persistência em arquivo de log. O formato segue o padrão:

```
⚠ Erro ao processar sala {email}: {mensagem}
⚠️ Erro ao criar chamado InvGate: {mensagem}
```

---

## 7. Monitoramento

### Como saber se a automação está funcionando

O correto funcionamento da automação pode ser validado por meio dos seguintes mecanismos:

- Monitoramento da saída padrão (stdout) do script `app.py`, onde, a cada ciclo, são exibidos os status de processamento de cada sala;
- Acesso ao dashboard web da aplicação, disponível via execução do script `dashboard.py` (URL padrão: `http://localhost:5000`), permitindo a visualização em tempo real das reuniões detectadas;
- Consulta ao painel do InvGate, verificando a criação de chamados com o padrão de título: `"Ronda diária - {nome da sala}"`.

### Endpoints do dashboard

| Endpoint | Descrição |
|---|---|
| `GET /` | Interface web do dashboard |
| `GET /api/rooms` | Lista salas com reuniões do dia e status em tempo real |
| `GET /api/calendar` | Eventos formatados para o calendário (FullCalendar) |
| `GET /api/rooms/status` | Status de acesso de cada sala via Graph API |

### Logs disponíveis

Atualmente, não há persistência de logs em arquivo. As informações são exibidas exclusivamente no terminal (stdout).

### Métricas relevantes

- Volume diário de chamados criados por sala;
- Quantidade de salas com erro de acesso (HTTP 404 / mailbox inativa);
- Tempo médio de execução por ciclo (tipicamente inferior a 30 segundos para o conjunto de salas monitoradas).

---

## 8. Riscos

| Ponto de Falha | Dependência Crítica | Impacto |
|---|---|---|
| Token do Azure AD expirado ou revogado | Microsoft Graph API | Interrupção total da consulta de salas e ausência de criação de chamados |
| Credencial Basic Auth do InvGate inválida ou revogada | InvGate API | Falha na criação de chamados, mantendo apenas a etapa de consulta ativa |
| Salas migradas para ambiente on-premise | Microsoft 365 (Cloud) | Salas tornam-se indisponíveis para a integração |
| Arquivo `.daily_tickets.json` corrompido ou sem permissão de escrita | Sistema de arquivos local | Possibilidade de geração de chamados duplicados no mesmo dia |
| Indisponibilidade da máquina de execução | Infraestrutura local | Interrupção completa da automação, sem mecanismos de alerta |

---

## 9. Critérios de Sucesso

- **Tempo de execução:** por ciclo inferior a 60 (sessenta) segundos para até 10 (dez) salas monitoradas;
- **Redução de esforço manual:** eliminação integral do esforço manual na abertura de chamados de ronda diária;
- **Taxa de erro aceitável:** zero ocorrência de chamados duplicados por sala/dia;
- **Volume processado corretamente:** geração de, no mínimo, um chamado por sala com reunião agendada em cada dia útil.

---

## 10. Evidências e Testes

### Procedimentos de Validação

1. Executar o comando `python app.py` e verificar, no terminal, a mensagem de confirmação de criação de chamado;
2. Validar a existência do chamado no ambiente de staging do InvGate, com o padrão de nomenclatura definido;
3. Reexecutar o script no mesmo dia e verificar a mensagem de controle de duplicidade, confirmando o correto funcionamento do mecanismo.

### Tipos de Teste

- **Teste Integrado:** Execução completa da aplicação (`app.py`) com integração real aos ambientes staging do Microsoft 365 e InvGate;
- **Teste de API (manual):** Validação dos endpoints via ferramentas como Postman (`POST /incident`, `GET /categories`, `GET /users`);
- **Teste de Duplicidade:** Execução repetida do script no mesmo dia, garantindo a criação de apenas um chamado por sala.

### Exemplo de Entrada e Saída

**Entrada:** Sala `salareuniaodti@agu.gov.br` com evento "Yan Fellippe Gomes Basílio" às 10:00.

**Saída esperada (terminal):**

```
📅 Reunião agendada encontrada!
📌 Título: Yan Fellippe Gomes Basílio
📍 Sala: Sala de Reunião DTI
⏰ Início: 09/04/2026 10:00
⏳ Fim: 09/04/2026 10:30
🛠️ Vistoria: 09/04/2026 09:45
🎫 Chamado InvGate criado: #4614 — open
✅ Pronto para ação
```

---

## 11. Plano de Implantação

### Ambiente de Implantação

A solução pode ser implantada em servidores Windows ou Linux com Python 3.9 ou superior, com acesso à internet, em ambiente local ou em nuvem.

### Procedimento de Deploy

```bash
# 1. Clonar o repositório
git clone <url-do-repositorio>
cd <nome-do-projeto>

# 2. Criar e ativar ambiente virtual
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Criar e configurar o arquivo .env com as credenciais necessárias

# 5. Validar credenciais
python get_token.py

# 6. Configurar execução contínua via Task Scheduler (Windows) ou systemd/cron (Linux)
```

### Dependências para Ativação

- App Registration ativo no Azure AD com permissões `Calendars.Read` e `Place.Read.All` (tipo Aplicativo);
- Credencial Basic Auth válida no InvGate;
- Identificadores válidos de categoria, cliente e criador no InvGate.

---

## 12. Plano de Rollback

### Desativação da Automação

- Encerrar o processo `app.py` na máquina de execução;
- Desabilitar a tarefa agendada no Task Scheduler ou serviço configurado no systemd.

### Retorno ao Processo Manual

- A equipe retoma a abertura manual de chamados de ronda diária diretamente no painel do InvGate;
- Não é necessária reversão de configurações no Microsoft 365 ou InvGate.

### Impactos da Reversão

- Chamados previamente criados permanecem registrados no InvGate, sem alteração;
- O arquivo `.daily_tickets.json` pode ser removido sem impacto operacional;
- Não há perda de dados.

---

## 13. Observações Gerais

### Melhorias Futuras

- Implementação de logs persistentes com política de rotação;
- Integração com notificações (Microsoft Teams ou e-mail) para eventos de falha;
- Suporte a múltiplos fusos horários;
- Evolução do dashboard com painel administrativo e histórico de chamados.

### Limitações Conhecidas

- Salas com caixa de correio em ambiente on-premise (Exchange local) não são suportadas pela Microsoft Graph API;
- O controle de duplicidade é local, podendo haver inconsistência em execuções simultâneas em múltiplas máquinas;
- Ausência de sistema de alertas automatizados, exigindo monitoramento manual.

### Ajustes Planejados

- Evolução do controle de duplicidade para consulta direta na API do InvGate, condicionada à ampliação da janela de busca do endpoint;
- Parametrização dos termos bloqueados por meio de variáveis de ambiente, eliminando a necessidade de alteração de código-fonte.
