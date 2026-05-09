from urllib.parse import urlparse


class OriginPolicy:
    def __init__(self, allowlist):
        self.allowlist = {entry.rstrip("/") for entry in allowlist if entry}

    @classmethod
    def from_csv(cls, value):
        return cls([item.strip() for item in value.split(",") if item.strip()])

    def is_allowed(self, origin):
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False

        normalized = origin.rstrip("/")
        if normalized in self.allowlist:
            return True

        return parsed.hostname in self.allowlist
