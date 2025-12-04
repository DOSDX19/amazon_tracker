# proxy_manager.py
import requests
from itertools import cycle

class RotatingProxyRequester:
    """
    Simple rotating proxy helper used for requests (not Selenium).
    The GUI accepts lines like:
       ip:port
       ip:port:user:pass
    This class stores the raw proxies and yields them in a cycle.
    """

    def __init__(self, proxies):
        # Normalize: strip, skip empty
        self.proxies = [p.strip() for p in (proxies or []) if p and p.strip()]
        self.proxy_cycle = cycle(self.proxies) if self.proxies else None

    def get(self, url, timeout=15):
        session = requests.Session()
        if not self.proxy_cycle:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp

        last_exc = None
        for _ in range(len(self.proxies)):
            proxy = next(self.proxy_cycle)
            # if proxy includes auth as ip:port:user:pass, requests expects http://user:pass@ip:port
            if proxy.count(":") >= 3:
                parts = proxy.split(":")
                host = parts[0]
                port = parts[1]
                user = parts[2]
                pwd = parts[3]
                proxy_url = f"http://{user}:{pwd}@{host}:{port}"
            else:
                proxy_url = f"http://{proxy}"

            session.proxies = {"http": proxy_url, "https": proxy_url}
            try:
                resp = session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                last_exc = e
                continue
        raise last_exc if last_exc is not None else Exception("All proxies failed")
