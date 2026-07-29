# YouTube Chat Bot - TV IEBT

Bot de chat ao vivo para YouTube que responde automaticamente as mensagens dos
espectadores durante as lives. Usa **Playwright** para automacao do chat e
**Deepseek** (via API OpenCode Zen) para gerar respostas naturais e variadas.

Inclui **interface grafica com icone na bandeja do sistema** para controle
facilitado do bot, e **modo OBS integrado** que inicia/para automaticamente
conforme a transmissao ao vivo do OBS Studio — tudo em um unico aplicativo.

## Funcionalidades

- Respostas inteligentes com IA (Deepseek) — variadas e naturais
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
  gui_main.py               Entry point unico (GUI + OBS)
  youtube_chat_bot.py       Bot principal (assincrono)
  ai_responder.py           Integracao com IA (Deepseek / OpenCode Zen)
  browser_utils.py          Deteccao do navegador e script anti-deteccao
  login_helper.py           Login no Google/YouTube
  obs_monitor.py            Monitor OBS WebSocket (streaming start/stop)
  obs_bot.py                Wrapper para modo OBS (delega para gui_main.py)
  gui/
    __init__.py
    bot_controller.py       Controla o bot + integracao OBS
    main_window.py          Janela principal (log + config + status OBS)
    tray_manager.py         Icone na bandeja do sistema (PySide6)
    log_handler.py          Redireciona logs para a interface
  config.yaml               Configuracoes
  build_exe.bat             Script para compilar o .exe unico
  iniciar_bot.bat           Atalho pra iniciar o bot (modo definido no config)
  iniciar_bot_obs.bat       Atalho pra iniciar com modo OBS forcado
  requirements.txt          Dependencias Python
  tests/                    Testes unitarios
  dist/                     Executavel compilado (.exe)
  browser_profile/          Sessao do navegador (login salvo)
  logs/                     Logs das execucoes
```

## Como usar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configurar API Key

Defina a variavel de ambiente:

```bash
set OPENCODE_ZEN_API_KEY=sua_chave_aqui
```

Ou crie um arquivo `.env` na raiz do projeto:

```
OPENCODE_ZEN_API_KEY=sua_chave_aqui
```

### 3. Fazer login

```bash
python login_helper.py
```

Isso abre o navegador na pagina de login do Google. Faca login e feche a janela.
A sessao fica salva em `browser_profile/`.

### 4. Rodar

**Modo GUI (recomendado):**

Clique duas vezes em `dist/YouTubeChatBot.exe` ou execute:

```bash
python gui_main.py
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
python gui_main.py --obs
```

Para iniciar sem mostrar a janela (so bandeja):

```bash
python gui_main.py --no-window
```

**Modo console (caso prefira):**

```bash
python youtube_chat_bot.py
```

### 5. Configurar

Edite o `config.yaml` manualmente ou pela aba "Config" na interface grafica:

```yaml
channel:
  name: "tviebt"            # @ do canal

ai:
  enabled: true
  mode: ai                  # ai | hybrid | off
  model: deepseek-v4-flash-free
  fallback_to_rules: true   # fallback para regras se IA falhar
```

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
build_exe.bat
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

39 testes passando, 2 skipped (dependentes de API key real).

## Solucao de Problemas

**O bot nao encontra o navegador:**
O `browser_utils.py` procura Brave, Chrome e Chromium em locais comuns.
Se seu navegador estiver em local diferente, defina a variavel:
```
set BROWSER_PATH=C:\caminho\do\seu\navegador.exe
```

**A IA nao responde:**
- Verifique se `OPENCODE_ZEN_API_KEY` esta configurada
- Verifique os logs em `logs/`
- Em modo `ai` sem fallback, o bot fica quieto se a API cair

**O chat para de responder:**
O bot tem reconexao automatica (ate 3 tentativas). Verifique os logs.

**A janela nao abre:**
O app inicia com a janela visivel por padrao. Se usou `--no-window`,
o icone fica so na bandeja — clique em "Abrir" para mostrar a janela.

## Tecnologias

- Python 3.11+
- Playwright (automacao de navegador)
- aiohttp (cliente HTTP async)
- Deepseek via API OpenCode Zen
- PySide6 (interface grafica)
- qasync (event loop async + Qt)
- obsws-python (conexao OBS WebSocket)
- PyYAML

## Licenca

Projeto da TV IEBT - Igreja Evangelica Batista em Timbi
