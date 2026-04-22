from pathlib import Path

from aiohttp import web


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UIHandlers:
    def __init__(self):
        self.template_path = PROJECT_ROOT / "templates" / "webrtc" / "chat_real.html"
        self.static_dir = PROJECT_ROOT / "static" / "webrtc"

    async def index(self, request):
        return web.FileResponse(self.template_path)
