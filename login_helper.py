#!/usr/bin/env python3
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from browser_utils import BROWSER_PATH, ANTI_DETECT_SCRIPT

BASE_DIR = Path(__file__).parent
PROFILE_DIR = BASE_DIR / "browser_profile"


async def main():
    print("=" * 58)
    print("  LOGIN - YouTube Chat Bot")
    print("=" * 58)
    print()
    print("1. Uma janela do navegador vai abrir.")
    print("2. Faca login na sua conta Google / YouTube.")
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

        await context.add_init_script(ANTI_DETECT_SCRIPT)

        page = await context.new_page()
        await page.goto(
            "https://accounts.google.com/ServiceLogin?service=youtube",
            wait_until="load",
        )

        print(
            "Navegador aberto. Faca login na sua conta Google "
            "e depois feche a janela."
        )
        print(
            "Se aparecer 'Esse navegador ou app pode nao ser seguro',"
        )
        print(
            "   clique em 'Tentar novamente' "
            "ou use a opcao 'Verificar identidade'"
        )
        print()
        print("Aguardando voce fechar o navegador...")

        await page.wait_for_event("close", timeout=0)
        await context.close()

    print("Login salvo! Agora voce pode rodar o bot principal.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
