# worker.py
from PySide6.QtCore import QObject, Signal, Slot
import traceback
import time
import os
import requests
from datetime import datetime

from amazon_api import AmazonAPI
from proxy_manager import RotatingProxyRequester
from report import Report


class ScraperWorker(QObject):
    # Signals sent to GUI
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

        # AmazonAPI engine
        self.scraper = AmazonAPI(
            search_term=self.search_term,
            filters=self.filters,
            base_url=self.filters.get('base_url', 'https://www.amazon.com'),
            requester=self.proxy_rotator,
            country=self.filters.get('country', None),
            currency=self.filters.get('currency', None),
            use_uc=self.filters.get('use_uc', True),
            headless=self.filters.get('headless', False),
            pages_per_proxy=self.filters.get('pages_per_proxy', 2),
        )

    def stop(self):
        self.stop_flag = True
        self.log.emit("[⚠] Stop request received…")
        try:
            self.scraper.stop()
            self.scraper.cleanup()
        except Exception:
            pass
        self.stopped.emit()

    @Slot()
    def run(self):
        try:
            self.log.emit("Preparing scraper…")

            products = []

            # ASIN mode
            if self.asin_list:
                self.log.emit(f"Tracking {len(self.asin_list)} ASINs…")
                data = self.scraper.track_asins(self.asin_list)
                for p in data:
                    if self.stop_flag:
                        self.stopped.emit()
                        return
                    self.partial.emit(p)
                    products.append(p)

                # Save report
                self._save_report(products)
                self.finished.emit(products)
                return

            # Keyword mode — use start_page / max_pages / max_products
            start_page = int(self.filters.get('start_page', 1) or 1)
            max_pages = int(self.filters.get('max_pages', 1) or 1)
            max_products = int(self.filters.get('max_products', 0) or 0)  # 0 => no limit

            # scrape pages
            scraped_count = 0
            for page_offset in range(0, max_pages):
                page = start_page + page_offset
                if self.stop_flag:
                    self.log.emit("❌ Scraping stopped by user.")
                    self.stopped.emit()
                    return

                self.log.emit(f"Scraping page {page} (start {start_page})…")
                try:
                    page_listings = self.scraper.scrape_products(url=None, page=page, filters=self.filters)
                except Exception as e:
                    self.log.emit(f"[ERROR] Failed to scrape page {page}: {e}")
                    continue

                for p in page_listings:
                    if self.stop_flag:
                        self.stopped.emit()
                        return

                    # visit product page to get full details
                    try:
                        item = self.scraper._get_full_product_from_listing(p)
                    except Exception:
                        item = None

                    if item is None:
                        continue

                    # apply advanced filters
                    try:
                        if not self.scraper._passes_advanced_filters(item):
                            continue
                    except Exception:
                        pass

                    products.append(item)
                    self.partial.emit(item)
                    scraped_count += 1

                    # progress
                    if max_products > 0:
                        prog = int(min(scraped_count / max_products * 100, 100))
                    else:
                        # Use pages progress approximation
                        prog = int(min((page_offset + 1) / max_pages * 100, 100)) if max_pages > 0 else 0
                    self.progress.emit(prog)

                    if max_products > 0 and scraped_count >= max_products:
                        break

                if max_products > 0 and scraped_count >= max_products:
                    break

                # small delay to reduce blocking
                time.sleep(0.4)

            # download images if requested
            if self.download_images and self.image_dir:
                self.log.emit("Downloading product images…")
                self._download_images(products)

            self.log.emit("✔ Scraping completed.")

            # Save report
            self._save_report(products)

            self.finished.emit(products)

        except Exception as e:
            trace = traceback.format_exc()
            self.error.emit(f"{e}\n\n{trace}")

    def _download_images(self, products):
        folder = self.image_dir or self.filters.get('output_folder') or 'images'
        os.makedirs(folder, exist_ok=True)

        for p in products:
            if self.stop_flag:
                return

            img = p.get('image') or p.get('image_url')
            asin = p.get('asin') or p.get('title','unknown')[:30]

            if not img:
                self.log.emit(f"[❌] No image for {asin}")
                continue

            try:
                last = img.split('/')[-1]
                ext = 'jpg'
                if '.' in last:
                    ext = last.split('.')[-1].split('?')[0]
                    if len(ext) > 5:
                        ext = 'jpg'
                path = os.path.join(folder, f"{asin}.{ext}")
                r = requests.get(img, timeout=12)
                if r.status_code == 200:
                    with open(path, 'wb') as f:
                        f.write(r.content)
                    self.log.emit(f"[✔] Saved image {path}")
                else:
                    self.log.emit(f"[❌] Image HTTP {r.status_code}: {img}")
            except Exception as e:
                self.log.emit(f"[❌] Image error for {asin}: {e}")

    def _save_report(self, products):
        try:
            out_folder = self.filters.get('output_folder') or 'reports'
            os.makedirs(out_folder, exist_ok=True)
            # create filename
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            name = 'results'
            if self.search_term:
                clean = ''.join(c for c in self.search_term if c.isalnum() or c in (' ', '_', '-')).strip()
                if clean:
                    name = clean.replace(' ', '_')
            if self.asin_list:
                name = 'asins_' + '_'.join(self.asin_list[:5])

            filename = f"{name}_{ts}"

            # Trim whitespace from all string fields
            cleaned = []
            for p in products:
                cp = {}
                for k, v in (p.items()):
                    if isinstance(v, str):
                        cp[k] = v.strip()
                    else:
                        cp[k] = v
                cleaned.append(cp)

            Report(file_name=filename, directory=out_folder, currency=self.filters.get('currency'),
                   filters=self.filters, base_url=self.filters.get('base_url'), data=cleaned,
                   export_format=self.filters.get('export_format','csv'))
            self.log.emit(f"[✔] Report saved: {out_folder}/{filename}.{self.filters.get('export_format','csv')}")
        except Exception as e:
            self.log.emit(f"[❌] Failed to save report: {e}")
