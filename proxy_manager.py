# proxy_manager.py
import requests
from itertools import cycle

class RotatingProxyRequester:
    """
    Simple, iterative rotating proxy requester.
    Use: rot = RotatingProxyRequester(list_of_proxies)
         resp = rot.get(url)
    If no proxies passed, performs direct requests.
    """

    def __init__(self, proxies):
        self.proxies = [p.strip() for p in (proxies or []) if p and p.strip()]
        self.proxy_cycle = cycle(self.proxies) if self.proxies else None

    def get(self, url, timeout=15):
        """
        Iteratively try proxies, return first successful response.
        Raises requests.RequestException if all proxies fail (or underlying error).
        """
        session = requests.Session()

        if not self.proxy_cycle:
            # Direct connection
            try:
                resp = session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                raise

        # Try each proxy once in a loop (no recursion)
        last_exc = None
        for _ in range(len(self.proxies)):
            proxy = next(self.proxy_cycle)
            session.proxies = {"http": proxy, "https": proxy}
            print(f"[REQUEST] Using Proxy: {proxy}")
            try:
                resp = session.get(url, timeout=timeout)
                resp.raise_for_status()
                return resp
            except Exception as e:
                print(f"[ERROR] Proxy Failed: {proxy} → {e}")
                last_exc = e
                # try next proxy
                continue

        # If we reach here, all proxies failed
        raise last_exc if last_exc is not None else Exception("All proxies failed")
