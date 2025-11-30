# worker.py
from PySide6.QtCore import QObject, Signal, Slot
import traceback
import time
import os
import requests

from amazon_api import AmazonAPI
from proxy_manager import RotatingProxyRequester


class ScraperWorker(QObject):
    # Signals
    finished = Signal(list)         # Final product list
    error = Signal(str)             # Fatal error
    progress = Signal(int)          # % progress
    log = Signal(str)               # log output text
    partial = Signal(dict)          # live row for table
    stopped = Signal()              # when user stops

    def __init__(
        self,
        search_term,
        asin_list,
        filters,
        proxies,
        download_images=False,
        image_dir=None
    ):
        super().__init__()

        self.search_term = search_term
        self.asin_list = asin_list
        self.filters = filters or {}
        self.download_images = download_images
        self.image_dir = image_dir
        self.stop_flag = False

        # Proxy rotator
        self.proxy_rotator = RotatingProxyRequester(proxies)

        # Amazon API engine (pass search_term & filters)
        base_url = self.filters.get("base_url") or self.filters.get("domain") or "https://www.amazon.com"
        self.scraper = AmazonAPI(
            search_term=self.search_term,
            filters=self.filters,
            base_url=base_url,
            requester=self.proxy_rotator,
            country=self.filters.get("country", None),
            currency=self.filters.get("currency", None),
            headless=self.filters.get("headless", True),
            use_uc=self.filters.get("use_uc", False),
            pages_per_proxy=self.filters.get("pages_per_proxy", 1),
        )

    def stop(self):
        self.stop_flag = True
        self.log.emit("[⚠] Stop request received…")
        try:
            self.scraper.stop()
            self.scraper.cleanup()
        except Exception:
            pass

    @Slot()
    def run(self):
        try:
            self.log.emit("Preparing scraper…")
            products = []

            # If ASINs provided -> track ASINs
            if self.asin_list:
                self.log.emit(f"Tracking {len(self.asin_list)} ASINs…")
                data = self.scraper.track_asins(self.asin_list)
                for p in data:
                    if self.stop_flag:
                        self.stopped.emit()
                        return
                    self.partial.emit(p)
                    products.append(p)
                self.finished.emit(products)
                return

            # Build search URL (safe)
            url = self.scraper.build_search_url(page=1)
            self.log.emit(f"Built URL: {url}")

            max_pages = int(self.filters.get("max_pages", 1))

            for page in range(1, max_pages + 1):
                if self.stop_flag:
                    self.log.emit("❌ Scraping stopped by user.")
                    self.stopped.emit()
                    return

                self.log.emit(f"Scraping page {page}/{max_pages}…")
                # Use AmazonAPI.scrape (we use run() per-page via create_driver flow)
                # We'll use amazon_api._extract_search_page_products by navigating to page url
                page_url = self.scraper.build_search_url(page=page)
                try:
                    # ensure driver created and navigate
                    try:
                        self.scraper.create_driver(proxy=self.scraper._get_next_proxy(None))
                    except Exception:
                        self.scraper.create_driver(proxy=None)

                    self.scraper.driver.get(page_url)
                    time.sleep(1.2 + (random := 0))  # small jitter
                    page_data = self.scraper._extract_search_page_products()
                except Exception:
                    page_data = []

                for p in page_data:
                    if self.stop_flag:
                        self.stopped.emit()
                        return
                    products.append(p)
                    self.partial.emit(p)

                # progress emit
                try:
                    self.progress.emit(int(page / max_pages * 100))
                except Exception:
                    pass

                # small anti-block delay
                time.sleep(0.25)

            # Download images if requested
            if self.download_images and self.image_dir:
                self.log.emit("Downloading product images…")
                self._download_images(products)

            self.log.emit("✔ Scraping completed.")
            self.finished.emit(products)

        except Exception as e:
            trace = traceback.format_exc()
            self.error.emit(f"{e}\n\n{trace}")
        finally:
            try:
                self.scraper.cleanup()
            except Exception:
                pass

    def _download_images(self, products):
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

        for p in products:
            if self.stop_flag:
                return
            img = p.get("image") or p.get("image_url")
            asin = p.get("asin", "unknown")
            if not img or not asin:
                continue
            try:
                r = requests.get(img, timeout=10)
                ext = img.split('.')[-1].split('?')[0]
                if len(ext) > 5 or '/' in ext:
                    ext = "jpg"
                path = os.path.join(self.image_dir, f"{asin}.{ext}")
                with open(path, "wb") as f:
                    f.write(r.content)
            except Exception:
                continue
