import asyncio
from playwright.async_api import async_playwright

async def main():
    auth_state = r"C:\Automation\Bots\Parser Bot\auth\state.json"
    url = "https://yachtiq.io/#/yacht/428427"

    subtabs = [
        "Accommodation",
        "Galley & Laundry Equipment",
        "Communication Equipment",
        "Navigation Equipment",
        "Entertainment Equipment",
        "Tenders & Toys",
        "Deck Equipment",
        "Rigs & Sails",
        "Safety & Security Equipment",
        "Refit History",
        "Comments",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(storage_state=auth_state)
        page = await context.new_page()

        print(f"Navigating to {url} ...")
        await page.goto(url)
        await asyncio.sleep(3)

        print("Clicking edit button (first button.ant-btn-icon-only)...")
        await page.locator("button.ant-btn-icon-only").first.click()
        await asyncio.sleep(1.5)

        print("Clicking Equipment tab...")
        await page.get_by_role("tab", name="Equipment").click()
        await asyncio.sleep(1.5)

        for subtab_name in subtabs:
            print(f"\n{'='*60}")
            print(f"SUBTAB: {subtab_name}")
            print('='*60)
            try:
                # Use JavaScript to find and click the right tab by text content
                # targeting only the rc-tabs-2 set (the visible view tabs)
                clicked = await page.evaluate("""(tabText) => {
                    const tabs = document.querySelectorAll('[role="tab"]');
                    for (const tab of tabs) {
                        if (tab.textContent.trim() === tabText && tab.id && tab.id.startsWith('rc-tabs-2-tab-')) {
                            tab.click();
                            return tab.id;
                        }
                    }
                    return null;
                }""", subtab_name)

                if not clicked:
                    print(f"[Tab '{subtab_name}' not found in rc-tabs-2]")
                    continue

                await asyncio.sleep(0.8)

                # Read from the corresponding panel
                panel_id = clicked.replace("-tab-", "-panel-")
                text = await page.evaluate("""(panelId) => {
                    const panel = document.getElementById(panelId);
                    return panel ? panel.innerText : null;
                }""", panel_id)

                if text is not None:
                    print(text)
                else:
                    print(f"[Panel #{panel_id} not found]")

            except Exception as e:
                print(f"[Error reading subtab '{subtab_name}': {e}]")

        print("\n\nDone reading all subtabs.")
        await browser.close()

asyncio.run(main())
