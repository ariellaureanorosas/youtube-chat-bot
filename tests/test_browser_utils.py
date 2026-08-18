from youtube_chat_bot.browser_utils import ANTI_DETECT_SCRIPT, BROWSER_PATH, find_browser


def test_find_browser_returns_string():
    assert isinstance(find_browser(), str)


def test_browser_path_is_string():
    assert isinstance(BROWSER_PATH, str)


def test_anti_detect_script_is_string():
    assert isinstance(ANTI_DETECT_SCRIPT, str)


def test_anti_detect_script_has_webdriver_patch():
    assert "webdriver" in ANTI_DETECT_SCRIPT


def test_anti_detect_script_has_webgl_patch():
    assert "getParameter" in ANTI_DETECT_SCRIPT


def test_anti_detect_script_has_screen_patch():
    assert "availWidth" in ANTI_DETECT_SCRIPT