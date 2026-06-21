# YouTube Chat Bot - TV IEBT

Bot de chat ao vivo para YouTube que responde automaticamente as mensagens dos
espectadores durante as lives. Usa **Playwright** para automacao do chat e
**Deepseek** (via API OpenCode Zen) para gerar respostas naturais e variadas.

Inclui **interface grafica com icone na bandeja do sistema** para controle
facilitado do bot.

## Funcionalidades

- Respostas inteligentes com IA (Deepseek) — variadas e naturais
- Modos: IA total, hibrido (keywords + IA), ou regras fixas
- Interface grafica com icone na bandeja do sistema (Windows)
- Editor de configuracao embutido na interface
- Anti-loop: detecta mensagens do proprio bot e ignora
- Anti-detecao: navegador disfarcado (webdriver, WebGL, screen resolution)
- Login persistente: loga uma vez, reusa a sessao
- Rate limiting em 3 camadas: intervalo, por minuto, dedup de resposta
- Fallback: se IA falhar, usa respostas fixas
- Reconnect automatico: ate 3 tentativas se o chat cair
- Cache de IA com limpeza automatica
- Suporte a Brave, Chrome e Chromium

## Estrutura

```
youtube-chat-bot/
  youtube_chat_bot.py       Bot principal (assincrono)
  ai_responder.py           Integracao com IA (Deepseek / OpenCode Zen)
  browser_utils.py          Deteccao do navegador e script anti-deteccao
  login_helper.py           Login no Google/YouTube
  gui_main.py               Ponto de entrada da interface grafica
  gui/
    __init__.py
    bot_controller.py       Controla o bot pela GUI
    main_window.py          Janela principal (log + config)
    tray_manager.py         Icone na bandeja do sistema
    log_handler.py          Redireciona logs para a interface
  config.yaml               Configuracoes
  build_exe.bat             Script para compilar o .exe
  iniciar_bot.bat           Atalho pra iniciar o bot (modo console)
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

### 4. Rodar

**Modo GUI (recomendado):**

Clique duas vezes em `dist/YouTubeChatBot.exe` ou no atalho na Area de Trabalho.

O icone aparece na bandeja do sistema (perto do relogio). Clique com botao direito
para acessar o menu:

- **Abrir** — abre a janela com log e configuracao
- **Iniciar Bot** — comeca a monitorar o chat ao vivo
- **Sair** — fecha o bot completamente

**Modo console (caso prefira):**

```bash
python youtube_chat_bot.py
```

Ou clique duas vezes em `iniciar_bot.bat`.

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

### 6. Compilar .exe (para distribuir)

```bash
build_exe.bat
```

Gera um executavel unico em `dist/YouTubeChatBot.exe`.

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

**O "Sair" nao aparece no menu da bandeja:**
Compile o .exe novamente com `build_exe.bat` — versoes antigas tinham esse bug.

## Tecnologias

- Python 3.11+
- Playwright (automacao de navegador)
- aiohttp (cliente HTTP async)
- Deepseek via API OpenCode Zen
- PySide6 (interface grafica)
- qasync (event loop async + Qt)
- PyYAML

## Licenca

Projeto da TV IEBT - Igreja Evangelica Batista em Timbi
