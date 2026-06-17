#!/usr/bin/env python3
"""
LOGIN HELPER — YouTube Chat Bot
================================
Rode UMA VEZ pra fazer login na sua conta Google/YouTube.
Depois o login fica salvo e o bot principal reusa a sessão.

Uso:
  python login_helper.py
"""

import asyncio
import os
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).parent
PROFILE_DIR = BASE_DIR / "browser_profile"

BROWSER_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Chromium\Application\chrome.exe",
    r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
]


def _find_browser() -> str | None:
    for path in BROWSER_PATHS:
        if os.path.isfile(path):
            return path
    return shutil.which("brave") or shutil.which("brave-browser") or shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("google-chrome-stable")


BROWSER_PATH = _find_browser() or "chrome"

# ── ANTI-DETECTION: esconde do Google que é um navegador automatizado ──
ANTI_DETECT_SCRIPT = """
// 1. Remove o sinal mais óbvio de automação
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Plugin array: navegadores reais têm plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});
Object.defineProperty(navigator, 'languages', {
    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
});

// 3. Chrome runtime (o Brave tem isso)
window.chrome = {
    runtime: { onConnect: { addListener: () => {} } },
    loadTimes: () => {},
    csi: () => {},
    app: {},
};

// 4. Permissions query - não exponha que somos automatizados
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: 'prompt' })
        : originalQuery(parameters)
);

// 5. WebGL vendor - parece mais real
const getExt = HTMLCanvasElement.prototype.getContext;
HTMLCanvasElement.prototype.getContext = function(...args) {
    const ctx = getExt.apply(this, args);
    if (ctx && args[0] === 'webgl') {
        const origGetParam = ctx.getParameter;
        ctx.getParameter = function(p) {
            if (p === 37445) return 'Google Inc. (Intel)';
            if (p === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics Direct3D11 vs_5_0 ps_5_0)';
            return origGetParam.call(this, p);
        };
    }
    return ctx;
};

// 6. Screen resolution - parece normal
Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
Object.defineProperty(screen, 'availHeight', { get: () => 1080 });
"""


async def main():
    print("=" * 58)
    print("  LOGIN — YouTube Chat Bot")
    print("=" * 58)
    print()
    print("1. Uma janela do navegador vai abrir.")
    print("2. Faça login na sua conta Google / YouTube.")
    print("3. Depois de logado, feche a janela.")
    print("4. Pronto! O login vai ficar salvo.")
    print()

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as pw:
        context = await pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            executable_path=BROWSER_PATH,
            headless=False,
            locale="pt",
            viewport={"width": 1280, "height": 900},
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        # Aplica anti-detection em TODAS as abas
        await context.add_init_script(ANTI_DETECT_SCRIPT)

        page = await context.new_page()
        await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", wait_until="load")

        print("🔵 Navegador aberto. Faça login na sua conta Google e depois feche a janela.")
        print("⚠️  Se aparecer 'Esse navegador ou app pode não ser seguro',")
        print("   clique em 'Tentar novamente' ou use a opção 'Verificar identidade'")
        print()
        print("⏳ Aguardando você fechar o navegador...")

        # Fica esperando até o usuário fechar
        await page.wait_for_event("close", timeout=0)

        await context.close()

    print("✅ Login salvo! Agora você pode rodar o bot principal.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
