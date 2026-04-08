from pathlib import Path
from playwright.sync_api import sync_playwright

auth_dir = Path("auth")
auth_dir.mkdir(exist_ok=True)

state_file = auth_dir / "state.json"

print("Will save login state to:", state_file.resolve())

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto("https://yachtiq.io/#/")

    input("Log in manually in the browser, then press Enter here to save your login session...")

    context.storage_state(path=str(state_file))

    print("Login state saved.")
    print("File exists:", state_file.exists())
    print("Saved to:", state_file.resolve())

    browser.close()