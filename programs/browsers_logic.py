from programs.catalog_logic import load_catalog_with_status, run_catalog_action
from programs.config import BROWSER_CATALOG_PATH, BROWSER_ICONS_DIR


def load_browsers_with_status():
    browsers = load_catalog_with_status(BROWSER_CATALOG_PATH, BROWSER_ICONS_DIR)
    return sorted(browsers, key=lambda browser: not browser["installed"])


def run_browser_action(browser):
    run_catalog_action(browser)
