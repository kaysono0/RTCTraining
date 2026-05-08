"""iPhone media debugging test — run against local WebRTC server.

Usage:
    .venv/bin/python tests/test_iphone_media_debug.py

Pre-requisite: WebRTC server running on https://0.0.0.0:8080
"""

from playwright.sync_api import sync_playwright

SERVER_URL = "https://localhost:8080"


def main():
    with sync_playwright() as p:
        iphone = p.devices["iPhone 15 Pro"]

        # Chromium with iPhone viewport + fake media + touch
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--use-fake-device-for-media-stream",
                "--use-fake-ui-for-media-stream",
            ],
        )
        context = browser.new_context(
            **iphone,
            ignore_https_errors=True,
            permissions=["camera", "microphone"],
        )
        page = context.new_page()

        print("→ Opening page as iPhone 15 Pro...")
        page.goto(SERVER_URL, timeout=15000)
        page.wait_for_load_state("networkidle")

        title = page.locator("h1").text_content()
        state = page.locator("#connectionState").text_content()
        print(f"  Title: {title}, State: {state}")

        # ---- STEP 1: Click Start Media ----
        print("\n→ Clicking 'Start Media'...")
        page.get_by_role("button", name="Start Media").click()
        page.wait_for_timeout(3000)

        state = page.locator("#connectionState").text_content()
        print(f"  connectionState: {state}")

        timeline = page.evaluate(
            """window.__RTCTrainingTestHooks.getTimeline().map(
                e => ({type: e.type, summary: e.summary, category: e.category})
            )"""
        )
        print(f"\n  Timeline ({len(timeline)} events):")
        for evt in timeline:
            marker = "  ← ERROR" if evt["category"] == "error" else ""
            print(f"    [{evt['category']:>10}] {evt['type']:<35} | {evt['summary']}{marker}")

        # ---- STEP 2: Click Join ----
        print("\n→ Clicking 'Join'...")
        page.fill("#roomIdInput", "iphone-test")
        page.fill("#displayNameInput", "iPhone-Tester")
        page.get_by_role("button", name="Join").click()
        page.wait_for_timeout(3000)

        state = page.locator("#connectionState").text_content()
        print(f"  connectionState after Join: {state}")

        timeline = page.evaluate(
            """window.__RTCTrainingTestHooks.getTimeline().map(
                e => ({type: e.type, summary: e.summary, category: e.category})
            )"""
        )
        print(f"\n  Final Timeline ({len(timeline)} events):")
        for evt in timeline:
            marker = "  ← ERROR" if evt["category"] == "error" else ""
            print(f"    [{evt['category']:>10}] {evt['type']:<35} | {evt['summary']}{marker}")

        # Video element state
        video = page.evaluate("""() => {
            const v = document.getElementById('localVideo');
            if (!v) return {found: false};
            return {found: true, readyState: v.readyState, paused: v.paused,
                    videoWidth: v.videoWidth, videoHeight: v.videoHeight,
                    srcObject: !!v.srcObject};
        }""")
        print(f"\n  #localVideo: {video}")

        # Stream track details
        stream = page.evaluate("""() => {
            const s = window.RTCTrainingShared?.state?.localStream;
            if (!s) return {hasStream: false};
            return {hasStream: true, active: s.active,
                tracks: s.getTracks().map(t => ({
                    kind: t.kind, label: t.label, readyState: t.readyState,
                    settings: t.getSettings ? t.getSettings() : {}
                }))};
        }""")
        print(f"  localStream: {stream}")

        page.screenshot(path="/tmp/iphone_test_result.png", full_page=True)
        print("\n  Screenshot saved to /tmp/iphone_test_result.png")
        browser.close()


if __name__ == "__main__":
    main()
