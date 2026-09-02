# YouTube Chat Bot - TV IEBT

Bot de chat ao vivo para YouTube que responde automaticamente as mensagens dos
espectadores durante as lives. Usa **Playwright** para automacao do chat e
**IA (via API NVIDIA / OpenCode Zen)** para gerar respostas naturais e variadas.

Inclui **interface grafica com icone na bandeja do sistema** para controle
facilitado do bot, e **modo OBS integrado** que inicia/para automaticamente
conforme a transmissao ao vivo do OBS Studio — tudo em um unico aplicativo.

## Funcionalidades

- Respostas inteligentes com IA — variadas e naturais
- Modos: IA total, hibrido (keywords + IA), ou regras fixas
- **Integracao OBS Studio** — inicia e para o bot com a transmissao ao vivo
- Interface grafica com icone na bandeja do sistema (Windows)
- Editor de configuracao embutido na interface
- Anti-loop: detecta mensagens do proprio bot e ignora
- Anti-detecao: navegador disfarcado (webdriver, WebGL, screen resolution)
- Login persistente: loga uma vez, reusa a sessao
- Rate limiting em 3 camadas: intervalo, por minuto, dedup de resposta
- Fallback: se IA falhar, usa respostas fixas; se OBS offline, modo manual
- Reconnect automatico: ate 3 tentativas se o chat cair
- Cache de IA com limpeza automatica
- Suporte a Brave, Chrome e Chromium

## Estrutura

```
youtube-chat-bot/
  src/youtube_chat_bot/
    __main__.py               Entry point: python -m youtube_chat_bot
    app.py                    Aplicacao GUI (janela + bandeja + OBS)
    bot.py                    Orquestrador principal (thin controller)
    ai_responder.py           Integracao com IA (NVIDIA / OpenAI-compat)
    response_router.py        Decisao de resposta (descarte, intencoes, regras)
    storage.py                Persistencia de mensagens processadas
    live_chat.py              Interacao com o YouTube (Playwright/DOM)
    browser_utils.py          Deteccao do navegador e script anti-deteccao
    config.py                 Caminhos (config, perfil, logs) + load_config
    login.py                  Login no Google/YouTube
    gui/
      bot_controller.py       Controla o bot + integracao OBS
      main_window.py          Janela principal (log + config + status OBS)
      tray_manager.py         Icone na bandeja do sistema (PySide6)
      log_handler.py          Redireciona logs para a interface
    obs/
      monitor.py              Monitor OBS WebSocket (streaming start/stop)
  scripts/
    build_exe.bat             Script para compilar o .exe unico
    iniciar_bot.bat           Atalho pra iniciar o bot (modo definido no config)
    iniciar_bot_obs.bat       Atalho pra iniciar com modo OBS forcado
  tests/                      Testes unitarios
  pyproject.toml              Configuracao do projeto (instalacao, testes)
  config.yaml.example         Template seguro de configuracao
  requirements.txt            Dependencias Python
```

### Arquitetura (Clean Architecture simplificada)

O `bot.py` e um orquestrador fino (~300 linhas) que delega responsabilidades
a modulos especializados:

- **`ResponseRouter`** — decide o que responder: descarte, modo puro, regras,
  deteccao de perguntas biblicas/horarios, cooldowns. Nao depende de I/O.
- **`MessageStore`** — persiste o historico de mensagens ja respondidas em disco.
  Enapsula leitura/escrita do `responded_messages.json`.
- **`LiveChatClient`** — toda a interacao com o browser via Playwright:
  navegar ate a live, abrir chat pop-out, detectar canal proprio, extrair
  mensagens do DOM e enviar respostas visuais/JS.
- **`AIResponder`** — integracao com a API NVIDIA/OpenAI-compativel.
  Trata retries, parsing e limpeza de respostas do modelo.

## Como usar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
pip install -e .              # instala o pacote (entry points + python -m)
playwright install chromium
```

### 2. Configurar API Key

Defina a variavel de ambiente (NVIDIA ou OpenCode Zen):

```bash
set NVIDIA_API_KEY=sua_chave_aqui
```

Ou crie um arquivo `.env` na raiz do projeto:

```
NVIDIA_API_KEY=sua_chave_aqui
```

> A chave `NVIDIA_API_KEY` tambem pode ser configurada diretamente em
> `config.yaml` -> `ai.api_key` (a `api_key` do config tem prioridade sobre
> a variavel de ambiente e o `.env`).

### 3. Fazer login

```bash
python -m youtube_chat_bot.login
```

Isso abre o navegador na pagina de login do Google. Faca login e feche a janela.
A sessao fica salva em `browser_profile/`.

### 4. Rodar

**Modo GUI (recomendado):**

Clique duas vezes em `dist/YouTubeChatBot.exe` ou execute:

```bash
python -m youtube_chat_bot
```

O icone aparece na bandeja do sistema (perto do relogio) e a janela abre
automaticamente. Clique com botao direito na bandeja para acessar o menu:

- **Abrir** — abre a janela com log e configuracao
- **Iniciar Bot** — comeca a monitorar o chat ao vivo
- **Sair** — fecha o bot completamente

**Modo OBS (inicia/para com a transmissao):**

O modo OBS e integrado ao mesmo aplicativo. Configure no `config.yaml`:

```yaml
obs:
  enabled: true    # ativa modo OBS automatico
  host: "localhost"
  port: 4455
  password: "123456"
  poll_interval: 2
```

Com `obs.enabled: true`, o bot:
1. Conecta no OBS WebSocket ao iniciar
2. Mostra "Aguardando transmissao..." na interface
3. Inicia automaticamente quando a transmissao comeca
4. Para automaticamente quando a transmissao encerra

Se o OBS nao estiver disponivel, cai em modo fallback (polling YouTube).

Para forcar o modo OBS independente do config:

```bash
python -m youtube_chat_bot --obs
```

Para iniciar sem mostrar a janela (so bandeja):

```bash
python -m youtube_chat_bot --no-window
```

**Modo console (caso prefira):**

```bash
python -m youtube_chat_bot.bot
```

### 5. Configurar

Edite o `config.yaml` manualmente ou pela aba "Config" na interface grafica:

```yaml
channel:
  name: "tviebt"            # @ do canal

ai:
  enabled: true
  mode: ai                  # ai | hybrid | off
  model: poolside/laguna-xs-2.1
  api_url: https://integrate.api.nvidia.com/v1/chat/completions
  # Horarios REAIS dos cultos — o bot so responde com estes horarios
  culto_horarios:
    - "Quarta-feira - 19:30"
    - "Domingo (manha) - 10:00"
    - "Domingo (noite) - 18:00"
  # Resposta (sem IA) para perguntas de conteudo biblico/doutrinario
  resposta_pergunta_biblica: "Essa e uma otima pergunta! Procure nossa equipe pastoral na igreja. Deus abencoe! :pray:"
```

> No modo `ai` NAO ha fallback para as regras fixas — se a IA nao responder
> (SKIP ou falha), nada e postado. As perguntas de **horario** e de
> **conteudo biblico** sao respondidas de forma deterministica (sem depender
> do modelo), evitando que a IA invente horarios ou versiculos.

### 6. Configurar OBS Studio (opcional)

Para usar o modo OBS, ative o WebSocket no OBS Studio:

1. **OBS Studio → Ferramentas → WebSocket Server Settings**
2. Marque "Enable WebSocket server"
3. Defina uma senha (opcional, mas recomendado)
4. Anote a porta (padrao: 4455)
5. Edite o `config.yaml`:

```yaml
obs:
  enabled: true
  host: "localhost"
  port: 4455
  password: "minha_senha"
  poll_interval: 2
```

### 7. Compilar .exe (para distribuir)

```bash
scripts\build_exe.bat
```

Gera um unico executavel em `dist/`:
- `YouTubeChatBot.exe` — versao unificada (GUI + OBS)

## Configuracao da IA

O system prompt no `config.yaml` define a personalidade do bot. Por padrao:

- Fala em 1 pessoa do plural ("nos da TV IEBT")
- Responde apenas quando apropriado (perguntas, oracoes, saudações)
- Ignora reacoes emocionais genericas
- Mantem tom respeitoso e institucional
- Retorna "SKIP" quando nao deve responder

## Testes

```bash
python -m pytest tests/ -v
```

## Solucao de Problemas

**O bot nao encontra o navegador:**
O `browser_utils.py` procura Brave, Chrome e Chromium em locais comuns.
Se seu navegador estiver em local diferente, defina a variavel:
```
set BROWSER_PATH=C:\caminho\do\seu\navegador.exe
```

**A IA nao responde:**
- Verifique se `NVIDIA_API_KEY` esta configurada (no `.env`, variavel de ambiente ou `ai.api_key` no `config.yaml`)
- Verifique os logs em `logs/`
- Em modo `ai` sem fallback, o bot fica quieto se a API cair

**O chat para de responder:**
O bot tem reconexao automatica (ate 3 tentativas). Verifique os logs.

**Aparece uma aba "about:blank" e depois a live:**
O bot reutiliza uma unica aba do navegador para checar e monitorar a live.
Se ainda vir abas brancas, verifique se ha outra instancia do bot rodando
(abra o Gerenciador de Tarefas e encerre `YouTubeChatBot.exe` ou `python`).

**A janela nao abre:**
O app inicia com a janela visivel por padrao. Se usou `--no-window`,
o icone fica so na bandeja — clique em "Abrir" para mostrar a janela.

## Tecnologias

- Python 3.11+
- Playwright (automacao de navegador)
- aiohttp (cliente HTTP async)
- IA via API NVIDIA / OpenCode Zen
- PySide6 (interface grafica)
- qasync (event loop async + Qt)
- obsws-python (conexao OBS WebSocket)
- PyYAML

## Licenca

Projeto da TV IEBT - Igreja Evangelica Batista em Timbi