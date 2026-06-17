import os
import shutil

BROWSER_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Chromium\Application\chrome.exe",
    r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
]

BROWSER_NAMES = [
    "brave", "brave-browser", "google-chrome",
    "google-chrome-stable", "chromium", "chromium-browser",
]


def find_browser() -> str:
    for path in BROWSER_PATHS:
        if os.path.isfile(path):
            return path
    for name in BROWSER_NAMES:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return "chrome"


BROWSER_PATH = find_browser()

ANTI_DETECT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['pt-BR', 'pt', 'en-US', 'en'] });
window.chrome = {
    runtime: { onConnect: { addListener: () => {} } },
    loadTimes: () => {}, csi: () => {}, app: {},
};
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: 'prompt' })
        : originalQuery(parameters)
);
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
Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
Object.defineProperty(screen, 'availHeight', { get: () => 1080 });
"""
