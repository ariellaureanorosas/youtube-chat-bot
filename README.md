# 🎥 YouTube Chat Bot — TV IEBT

Bot de chat ao vivo para YouTube que responde automaticamente às mensagens dos espectadores durante as lives da **TV IEBT** (Igreja Evangélica Batista em Timbí).

Usa **Playwright** + **Brave** para automação do chat e **Deepseek** (via API OpenAI) para gerar respostas naturais e acolhedoras com a personalidade da equipe de comunicação da igreja.

## ✨ Funcionalidades

- **🤖 Respostas inteligentes** — IA entende o contexto e responde apenas quando apropriado
- **🙅 Evita duplicação** — não repete a mesma mensagem duas vezes
- **🪞 Anti-loop** — detecta mensagens do próprio bot e ignora
- **🛡️ Anti-detecção** — navegador disfarçado (navigator.webdriver, chrome.runtime, etc.)
- **💾 Login persistente** — você loga uma vez e o bot reusa a sessão
- **🚀 Início automático** — pode ligar sozinho quando o PC inicia (Task Scheduler)
- **📝 Menção ao autor** — responde citando o nome da pessoa quando é uma mensagem individual

## 🧱 Estrutura

```
youtube-chat-bot/
├── youtube_chat_bot.py   # Bot principal (loop, chat, anti-detection)
├── ai_responder.py        # Integração com a IA
├── login_helper.py        # Login no Google/YouTube
├── config.yaml            # Configurações (modelo, prompt, canais)
├── iniciar_bot.bat        # Atalho pra iniciar o bot
├── browser_profile/       # Sessão do navegador (login salvo)
├── logs/                  # Logs das execuções
└── venv/                  # Ambiente virtual Python
```

## ⚙️ Como usar

### 1. Instalar dependências

```bash
pip install playwright pyyaml openai
playwright install chromium
```

### 2. Fazer login

```bash
python login_helper.py
```

Isso abre o navegador Brave (ou Chrome) na página de login do Google. Faça login na conta do YouTube da TV IEBT e feche o navegador. A sessão fica salva em `browser_profile/`.

### 3. Configurar

Edite o `config.yaml`:

```yaml
youtube:
  channel_name: "tviebt"          # Nome do seu canal
  live_check_interval: 30         # Segundos entre verificações de live ativa

ai:
  model: "deepseek-v4-flash-free" # Modelo da IA
  provider: "opencode-zen"        # Provedor (OpenAI-compatible)
  max_tokens: 1000
  system_prompt: "..."            # Personalidade do bot
```

### 4. Rodar

```bash
python youtube_chat_bot.py
```

Ou clique duas vezes em `iniciar_bot.bat`.

## 🔧 Personalidade da IA

O bot usa um **system prompt** que define a persona da equipe de comunicação da igreja: tom respeitoso, acolhedor e institucional, evitando debates, respondendo apenas saudações e perguntas pertinentes com amor cristão.

Você pode editar esse prompt no `config.yaml` para ajustar o tom.

## 🛠️ Tecnologias

- **Python 3.11+**
- **Playwright** — automação do navegador
- **Brave Browser** (navegador principal)
- **Deepseek** via API OpenAI (OpenCode Zen)
- **Hermes Agent** — CLI agent que gerencia o bot

## 🤝 Contribuindo

Este é um projeto da **TV IEBT**. Sinta-se à vontade para abrir issues ou sugerir melhorias!

---

**TV IEBT** — Igreja Evangélica Batista em Timbí 🙏
