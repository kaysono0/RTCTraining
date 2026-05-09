from urllib.parse import urlencode


def build_upstream_url(origin, upstream_path, query):
    upstream_query = {
        key: value
        for key, value in query.items()
        if key != "origin"
    }
    query_string = urlencode(upstream_query)
    url = f"{origin.rstrip('/')}{upstream_path}"
    if query_string:
        return f"{url}?{query_string}"
    return url
