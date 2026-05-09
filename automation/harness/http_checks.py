from aiohttp import ClientSession, ClientTimeout, TCPConnector


class HarnessCheckError(RuntimeError):
    pass


async def fetch_text(url):
    timeout = ClientTimeout(total=5)
    connector = TCPConnector(ssl=False)
    async with ClientSession(timeout=timeout, connector=connector) as session:
        async with session.get(url) as response:
            text = await response.text()
            if response.status >= 400:
                raise HarnessCheckError(
                    f"{url} returned HTTP {response.status}: {text[:200]}"
                )
            return text


async def fetch_json(url):
    timeout = ClientTimeout(total=5)
    connector = TCPConnector(ssl=False)
    async with ClientSession(timeout=timeout, connector=connector) as session:
        async with session.get(url) as response:
            payload = await response.json()
            if response.status >= 400:
                raise HarnessCheckError(
                    f"{url} returned HTTP {response.status}: {payload}"
                )
            return payload


async def check_text_contains(url, expected):
    text = await fetch_text(url)
    if expected not in text:
        raise HarnessCheckError(f"{url} did not contain expected text: {expected}")
    return text


async def check_json_ok(url):
    payload = await fetch_json(url)
    if payload.get("ok") is not True:
        raise HarnessCheckError(
            f"{url} expected ok JSON envelope, got: {payload}"
        )
    return payload
