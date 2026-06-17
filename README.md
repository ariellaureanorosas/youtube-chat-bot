# YouTube Chat Bot - TV IEBT

Bot de chat ao vivo para YouTube que responde automaticamente as mensagens dos
espectadores durante as lives. Usa **Playwright** para automacao do chat e
**Deepseek** (via API OpenCode Zen) para gerar respostas naturais.

## Funcionalidades

- Respostas inteligentes com IA (Deepseek)
- Modos: IA total, hibrido (keywords + IA), ou regras fixas
- Anti-loop: detecta mensagens do proprio bot e ignora
- Anti-detecao: navegador disfarcado (webdriver, WebGL, screen resolution)
- Login persistente: loga uma vez, reusa a sessao
- Rate limiting: evita flood no chat
- Fallback: se IA falhar, usa respostas fixas
- Reconnect automatico: ate 3 tentativas se o chat cair

## Estrutura

```
youtube-chat-bot/
  youtube_chat_bot.py   Bot principal
  ai_responder.py       Integracao com a IA
  login_helper.py       Login no Google/YouTube
  browser_utils.py      Utilitarios de navegador compartilhados
  config.yaml           Configuracoes
  iniciar_bot.bat       Atalho pra iniciar o bot
  requirements.txt      Dependencias
  tests/                Testes unitarios
  browser_profile/      Sessao do navegador (login salvo)
  logs/                 Logs das execucoes
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
# Linux/Mac
export OPENCODE_ZEN_API_KEY=sua_chave_aqui

# Windows (cmd)
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

### 4. Configurar

Edite o `config.yaml`:

```yaml
channel:
  name: "tviebt"            # @ do canal

ai:
  mode: ai                  # ai | hybrid | off
  model: deepseek-v4-flash-free
  fallback_to_rules: true   # fallback para regras se IA falhar
```

### 5. Rodar

```bash
python youtube_chat_bot.py
```

Ou clique duas vezes em `iniciar_bot.bat`.

## Configuracao da IA

O system prompt no `config.yaml` define a personalidade do bot. Por padrao:

- Fala em 1 pessoa do plural ("nos da TV IEBT")
- Responde apenas quando apropriado (perguntas, oracoes, saudações)
- Ignora reacoes emocionais genericas
- Mantem tom respeitoso e institucional
- Retorna "SKIP" quando nao deve responder

## Solucao de Problemas

**O bot nao encontra o navegador:**
O `browser_utils.py` procura Brave, Chrome e Chromium em locais comuns.
Se seu navegador estiver em local diferente, defina a variavel:
```
export BROWSER_PATH=/caminho/do/seu/navegador
```

**A IA nao responde:**
- Verifique se `OPENCODE_ZEN_API_KEY` esta configurada
- Verifique os logs em `logs/`
- Em modo `ai` sem fallback, o bot fica quieto se a API cair

**O chat para de responder:**
O bot tem reconexao automatica (ate 3 tentativas). Verifique os logs.

## Tecnologias

- Python 3.11+
- Playwright (automacao de navegador)
- aiohttp (cliente HTTP async)
- Deepseek via API OpenCode Zen
- PyYAML

## Licenca

Projeto da TV IEBT - Igreja Evangelica Batista em Timbi
