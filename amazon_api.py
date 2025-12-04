# amazon_api.py
import time
import random
import re
from typing import List, Optional, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
import undetected_chromedriver as uc

# CONFIG - tweak these lists if you want
PROXIES = []
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def random_proxy() -> Optional[str]:
    if not PROXIES:
        return None
    return random.choice(PROXIES)


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


class AmazonAPI:
    """Lightweight Amazon scraping engine compatible with the GUI/worker.

    - Uses undetected_chromedriver by default (falls back to regular chromedriver)
    - Respects an external `requester` object that can provide rotating proxies
    - Provides: build_search_url(), scrape_products(), track_asins(), get_single_product_info()
    - All text fields are stripped/cleaned before returning
    """

    def __init__(
        self,
        search_term: str = "",
        filters: Dict[str, Any] = None,
        base_url: str = "https://www.amazon.com",
        requester: Optional[Any] = None,
        country: Optional[str] = None,
        currency: Optional[str] = None,
        use_uc: bool = True,
        headless: bool = False,
        pages_per_proxy: int = 2,
    ):
        self.base_url = (base_url or "https://www.amazon.com").rstrip("/")
        self.search_term = search_term or ""
        self.filters = filters or {}
        self.currency = currency
        self.use_uc = use_uc
        self.headless = headless
        self.pages_per_proxy = pages_per_proxy or int(self.filters.get("pages_per_proxy", 2))
        self.requester = requester
        self.country = country

        self.driver = None
        self.wait = None
        self._stop_requested = False

    # ---------------- low-level driver helpers ----------------
    def _get_next_proxy(self, explicit_proxy: Optional[str] = None) -> Optional[str]:
        if explicit_proxy:
            return explicit_proxy
        if self.requester is not None:
            proxy_cycle = getattr(self.requester, "proxy_cycle", None)
            if proxy_cycle is not None:
                try:
                    return next(proxy_cycle)
                except Exception:
                    pass
        return random_proxy()

    def create_driver(self, proxy: Optional[str] = None):
        # close existing
        try:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
        except Exception:
            pass

        if self.use_uc:
            options = uc.ChromeOptions()
        else:
            options = webdriver.ChromeOptions()

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--lang=en-US")
        options.add_argument("--start-maximized")
        options.add_argument("--incognito")
        options.add_argument("--ignore-certificate-errors")

        if self.headless:
            options.add_argument("--headless=new")

        try:
            ua = random_user_agent()
            options.add_argument(f"user-agent={ua}")
        except Exception:
            pass

        chosen_proxy = self._get_next_proxy(proxy)
        if chosen_proxy:
            try:
                # Accept formats like ip:port or http://user:pass@ip:port
                options.add_argument(f"--proxy-server={chosen_proxy}")
            except Exception:
                pass

        try:
            if self.use_uc:
                try:
                    self.driver = uc.Chrome(options=options)
                except Exception:
                    self.driver = webdriver.Chrome(options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
        except Exception as e:
            raise RuntimeError(f"Failed to create driver: {e}")

        # short wait helper
        try:
            self.wait = WebDriverWait(self.driver, 12)
        except Exception:
            self.wait = None

        # warmup
        time.sleep(random.uniform(0.8, 1.6))
        return self.driver

    def cleanup(self):
        try:
            if self.driver:
                # try to stop service process if available (best-effort)
                try:
                    svc = getattr(self.driver, "service", None)
                    proc = getattr(svc, "process", None)
                    if proc:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self.driver.quit()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self.driver = None

    def stop(self):
        self._stop_requested = True
        # attempt immediate cleanup
        try:
            self.cleanup()
        except Exception:
            pass

    def should_stop(self) -> bool:
        return self._stop_requested

    # ---------------- URL builder / page scraping ----------------
    def build_search_url(self, page: int = 1) -> str:
        base = self.base_url.rstrip("/")
        q = (self.search_term or "").strip()
        q_enc = q.replace(" ", "+")
        url = f"{base}/s?k={q_enc}"

        min_p = self.filters.get("min", None)
        max_p = self.filters.get("max", None)
        price_fragment = self._price_fragment_for_domain(self.base_url, min_p, max_p)
        if price_fragment:
            url = url + price_fragment

        # safe page handling
        try:
            page_num = int(page) if page is not None else int(self.filters.get("page", 1))
        except Exception:
            try:
                page_num = int(self.filters.get("page", 1))
            except Exception:
                page_num = 1

        if page_num > 1:
            url = url + f"&page={page_num}"

        if self.filters.get("category_node"):
            url += f"&i={self.filters.get('category_node')}"

        return url

    def _price_fragment_for_domain(self, domain: str, min_p, max_p) -> str:
        if (min_p is None or min_p == "") and (max_p is None or max_p == ""):
            return ""
        try:
            min_val = float(min_p) if min_p is not None and str(min_p).strip() != "" else None
            max_val = float(max_p) if max_p is not None and str(max_p).strip() != "" else None
        except Exception:
            return ""

        domain_name = domain.split("//")[-1].split("/")[0].lower()
        if domain_name.endswith((".com", ".ca", ".com.au", ".co.uk")):
            parts = []
            if min_val is not None:
                parts.append(f"low-price={int(min_val)}")
            if max_val is not None:
                parts.append(f"high-price={int(max_val)}")
            if parts:
                return "&" + "&".join(parts)
            return ""

        if domain_name.endswith((".de", ".fr", ".it", ".es", ".nl", ".se", ".pl")):
            min_cents = int(min_val * 100) if min_val is not None else 0
            max_cents = int(max_val * 100) if max_val is not None else 0
            return f"&rh=p_36:{min_cents}-{max_cents}"

        parts = []
        if min_val is not None:
            parts.append(f"low-price={int(min_val)}")
        if max_val is not None:
            parts.append(f"high-price={int(max_val)}")
        if parts:
            return "&" + "&".join(parts)
        return ""

    def scrape_products(self, url: Optional[str] = None, page: int = 1, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Scrape a search results page and return partial product dicts (listing info).
        This is useful for iterating pages without immediately visiting product pages.
        """
        if filters:
            # merge incoming filters (caller passes references)
            try:
                self.filters.update(filters)
            except Exception:
                self.filters = filters

        if url:
            search_url = url
        else:
            search_url = self.build_search_url(page=page)

        # Ensure a driver
        if not self.driver:
            try:
                self.create_driver(proxy=self._get_next_proxy(None))
            except Exception:
                self.create_driver(proxy=None)

        try:
            self.driver.get(search_url)
        except Exception:
            return []

        time.sleep(random.uniform(1.0, 2.0))
        results = self._extract_search_page_products()

        # clean up driver to avoid many open browsers; caller may reopen as needed
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None

        return results

    def _extract_search_page_products(self) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        try:
            cards = self.driver.find_elements(By.XPATH, "//div[@data-component-type='s-search-result']")
        except Exception:
            cards = []

        for c in cards:
            try:
                asin = c.get_attribute("data-asin") or ""
                if not asin:
                    continue
                try:
                    t_el = c.find_element(By.XPATH, ".//h2//span")
                    title = t_el.text.strip()
                except Exception:
                    title = ""
                url = ""
                try:
                    link_el = c.find_element(By.XPATH, ".//a[@class='a-link-normal s-no-outline']")
                    href = link_el.get_attribute("href") or ""
                    if href:
                        url = href.split("?")[0]
                        if href.startswith("/"):
                            url = f"{self.base_url.rstrip('/')}{href}"
                except Exception:
                    url = ""

                price = None
                try:
                    whole = c.find_element(By.CLASS_NAME, "a-price-whole").text
                    frac = ""
                    try:
                        frac = c.find_element(By.CLASS_NAME, "a-price-fraction").text
                    except Exception:
                        frac = ""
                    price_text = whole + (("." + frac) if frac else "")
                    price = self._normalize_price_text(price_text)
                except Exception:
                    try:
                        el = c.find_element(By.XPATH, ".//span[contains(@class,'a-offscreen')]")
                        price = self._normalize_price_text(el.get_attribute("innerText") or el.text)
                    except Exception:
                        price = None

                img = ""
                try:
                    img_el = c.find_element(By.XPATH, ".//img")
                    img = img_el.get_attribute("src") or img_el.get_attribute("data-src") or ""
                except Exception:
                    img = ""

                results.append({
                    "asin": asin,
                    "title": title,
                    "url": url,
                    "price": price,
                    "image_url": img,
                    "image": img,
                })
            except Exception:
                continue

        return results

    def _normalize_price_text(self, raw: str) -> Optional[float]:
        if not raw:
            return None
        p = raw.strip()
        p = p.replace("€", "").replace("$", "").replace("£", "")
        if "." in p and "," in p:
            p = p.replace(".", "").replace(",", ".")
        else:
            p = p.replace(",", ".")
        p = re.sub(r"[^\d\.\-]", "", p)
        try:
            return float(p)
        except Exception:
            return None

    # ---------------- product page scraping ----------------
    def get_single_product_info(self, url: str) -> Optional[Dict[str, Any]]:
        # kept for backward compatibility with some callers (worker used get_single_product_info)
        return self._get_full_product_from_listing({"url": url})

    def _get_full_product_from_listing(self, listing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        url = listing.get("url")
        if not url:
            asin = listing.get("asin")
            if asin:
                url = f"{self.base_url}/dp/{asin}"
            else:
                return None
        return self._visit_and_extract(url)

    def _visit_and_extract(self, url: str) -> Optional[Dict[str, Any]]:
        if self.should_stop():
            return None

        if not self.driver:
            try:
                self.create_driver(proxy=self._get_next_proxy(None))
            except Exception:
                self.create_driver(proxy=None)

        try:
            self.driver.get(url)
        except Exception:
            return None

        time.sleep(random.uniform(1.0, 2.2))

        title = self._safe_text_by_id("productTitle") or ""
        price = self.get_price()
        rating = self._extract_rating()
        review_count = self._extract_review_count()
        images = self._extract_images()
        availability = self._extract_availability()
        seller_info = self._extract_seller_info()
        bsr = self._extract_bsr()

        # description
        description = ""
        try:
            desc_el = self.driver.find_element(By.ID, "productDescription")
            description = desc_el.text.strip()
        except Exception:
            try:
                meta = self.driver.find_element(By.XPATH, "//meta[@name='description']")
                description = meta.get_attribute("content") or ""
            except Exception:
                description = ""

        brand = ""
        try:
            brand = self._safe_text_by_id("bylineInfo") or ""
            brand = brand.strip()
        except Exception:
            brand = ""

        condition = ""
        try:
            cond = self.driver.find_elements(By.ID, "condition")
            if cond:
                condition = cond[0].text.strip()
        except Exception:
            condition = ""

        seller_type = ""
        if seller_info:
            s = seller_info.lower()
            if "fulfilled by amazon" in s or "fba" in s:
                seller_type = "fba"
            elif "sold by amazon" in s or "amazon.com" in s or "ships from and sold by amazon" in s:
                seller_type = "amazon"
            else:
                seller_type = "fbm"

        discount = False
        try:
            src = (self.driver.page_source or "").lower()
            if "you save" in src or "was $" in src or "was €" in src or "save" in src:
                discount = True
        except Exception:
            discount = False

        currency = self.currency or ""
        country = self.base_url.split("//")[-1].split(".")[-1].upper()

        if not title and not price:
            return None

        main_image = images[0] if images else ""

        product = {
            "asin": self.extract_asin(url),
            "url": url,
            "title": title or "",
            "description": description or "",
            "seller": seller_info or "",
            "price": price,
            "rating": rating,
            "reviews": review_count,
            "images": images,
            "image_url": main_image,
            "image": main_image,
            "currency": currency,
            "availability": availability,
            "seller_info": seller_info,
            "bsr": bsr,
            "brand": brand or "",
            "condition": condition or "",
            "seller_type": seller_type or "",
            "discount": discount,
            "category_node": self.filters.get("category_node") or "",
            "country": country,
            "include_keywords": self.filters.get("include_keywords") or [],
            "exclude_keywords": self.filters.get("exclude_keywords") or [],
            "other": None,
        }

        # clean all string fields
        for k, v in list(product.items()):
            if isinstance(v, str):
                product[k] = v.strip()

        return product

    def _safe_text_by_id(self, elem_id: str) -> Optional[str]:
        try:
            el = self.driver.find_element(By.ID, elem_id)
            return el.text.strip()
        except Exception:
            return None

    def safe_get(self, by, value) -> Optional[str]:
        try:
            el = self.driver.find_element(by, value)
            return el.text.strip()
        except Exception:
            return None

    def safe_get_text(self, by, value) -> Optional[str]:
        return self.safe_get(by, value)

    def get_price(self) -> Optional[float]:
        xpaths = [
            '//*[@id="corePrice_feature_div"]//span[contains(@class,"a-price-whole")]',
            '//*[@id="corePriceDisplay_desktop_feature_div"]//span[contains(@class,"a-price-whole")]',
            '//*[@id="priceblock_dealprice"]',
            '//*[@id="priceblock_ourprice"]',
            "//span[contains(@class,'a-offscreen') and (contains(text(),'$') or contains(text(),'€') or contains(text(),'£'))]",
        ]
        for xp in xpaths:
            try:
                els = self.driver.find_elements(By.XPATH, xp)
                if not els:
                    continue
                for el in els:
                    txt = el.get_attribute("innerText") or el.text or ""
                    val = self.parse_price(txt)
                    if val is not None:
                        return val
            except Exception:
                pass

        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "span.a-price span.a-offscreen")
            txt = el.get_attribute("innerText") or el.text or ""
            return self.parse_price(txt)
        except Exception:
            pass

        return None

    def parse_price(self, p: str) -> Optional[float]:
        if not p:
            return None
        s = p.strip()
        s = s.replace("\xa0", " ")
        s = s.replace("€", "").replace("$", "").replace("£", "").replace(",", ".")
        s = re.sub(r"[^\d\.\-]", "", s)
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            try:
                return float(s.split()[0])
            except Exception:
                return None

    def _extract_rating(self) -> Optional[float]:
        try:
            el = self.driver.find_element(By.ID, "acrPopover")
            txt = el.get_attribute("title") or el.text or ""
            m = re.search(r"(\d[\.,]?\d?)\s+out of", txt)
            if m:
                return float(m.group(1).replace(",", "."))
        except Exception:
            pass
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, "span.a-icon-alt")
            txt = el.text or ""
            m = re.search(r"(\d[\.,]?\d?)\s+out of", txt)
            if m:
                return float(m.group(1).replace(",", "."))
        except Exception:
            pass
        return None

    def _extract_review_count(self) -> Optional[int]:
        try:
            el = self.driver.find_element(By.ID, "acrCustomerReviewText")
            txt = el.text or ""
            m = re.search(r"([\d,\. ]+)", txt)
            if m:
                n = m.group(1).replace(",", "").replace(".", "").replace(" ", "")
                return int(n)
        except Exception:
            pass
        return None

    def _extract_bsr(self) -> Optional[int]:
        try:
            try:
                el = self.driver.find_element(By.ID, "productDetails_detailBullets_sections1")
                txt = el.text or ""
                m = re.search(r"Best Sellers Rank\s*#?\s*([\d,]+)", txt, re.I)
                if m:
                    return int(m.group(1).replace(",", ""))
            except Exception:
                pass
            src = (self.driver.page_source or "")
            m = re.search(r"Best Sellers Rank[:\s#]*([\d,]+)", src, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
        except Exception:
            pass
        return None

    def _extract_images(self, limit: int = 8) -> List[str]:
        imgs: List[str] = []
        try:
            candidates = self.driver.find_elements(By.XPATH, ".//img[contains(@class,'s-image')]")
            for t in candidates:
                src = t.get_attribute("src")
                if src and src.startswith("http") and "sprite" not in src and "data:image" not in src:
                    imgs.append(src)
            seen = list(dict.fromkeys(imgs))
            return seen[:limit]
        except Exception:
            return []

    def _extract_seller_info(self) -> Optional[str]:
        try:
            txt = self.safe_get_text(By.ID, "merchant-info")
            if txt:
                return txt
            try:
                el = self.driver.find_element(By.ID, "sellerProfileTriggerId")
                return el.text.strip()
            except Exception:
                pass
        except Exception:
            pass
        return None

    def _extract_availability(self) -> Optional[str]:
        try:
            el = self.driver.find_element(By.ID, "availability")
            return el.text.strip()
        except Exception:
            try:
                txt = self.driver.find_element(By.CSS_SELECTOR, "#availability .a-color-state").text.strip()
                return txt
            except Exception:
                return None

    def _passes_advanced_filters(self, product: Dict[str, Any]) -> bool:
        p = product.get("price")
        if p is not None:
            try:
                min_p = float(self.filters.get("min", -1e12)) if self.filters.get("min", "") != "" else -1e12
                max_p = float(self.filters.get("max", 1e12)) if self.filters.get("max", "") != "" else 1e12
            except Exception:
                min_p, max_p = -1e12, 1e12
            if p < min_p or p > max_p:
                return False

        rating = product.get("rating") or 0.0
        min_rating = float(self.filters.get("min_rating", 0)) if self.filters.get("min_rating", "") != "" else 0
        max_rating = float(self.filters.get("max_rating", 5)) if self.filters.get("max_rating", "") != "" else 5
        if rating < min_rating or rating > max_rating:
            return False

        reviews = int(product.get("reviews") or product.get("review_count") or 0)
        min_reviews = int(self.filters.get("min_reviews", 0))
        max_reviews = int(self.filters.get("max_reviews", 1000000000))
        if reviews < min_reviews or reviews > max_reviews:
            return False

        if self.filters.get("prime_only"):
            if not product.get("prime", False):
                return False

        if self.filters.get("in_stock_only"):
            av = (product.get("availability") or "").lower()
            if "in stock" not in av and "available" not in av and "usually ships" not in av:
                return False

        brand_filter = self.filters.get("brand")
        brands = self.filters.get("brands")
        title = (product.get("title") or "").lower()
        if brand_filter:
            if brand_filter.lower() not in title and brand_filter.lower() not in (product.get("brand") or "").lower():
                return False
        if brands and isinstance(brands, list):
            if not any(b.lower() in title or b.lower() in (product.get("brand") or "").lower() for b in brands):
                return False

        include_keywords = self.filters.get("include_keywords") or []
        exclude_keywords = self.filters.get("exclude_keywords") or []
        for kw in include_keywords:
            if kw.lower() not in title:
                return False
        for kw in exclude_keywords:
            if kw.lower() in title:
                return False

        bsr = product.get("bsr") or 0
        bsr_min = int(self.filters.get("bsr_min", 0))
        bsr_max = int(self.filters.get("bsr_max", 1000000000))
        if bsr:
            if bsr < bsr_min or bsr > bsr_max:
                return False

        seller_type = (self.filters.get("seller_type") or "").lower()
        seller_text = (product.get("seller_info") or "").lower()
        if seller_type:
            if seller_type == "amazon" and "amazon" not in seller_text:
                return False
            if seller_type == "fba" and "fulfillment by amazon" not in seller_text and "fba" not in seller_text:
                return False
            if seller_type == "fbm" and ("fulfillment by amazon" in seller_text or "fba" in seller_text):
                return False

        if self.filters.get("discount_only"):
            page_src = (self.driver.page_source or "").lower()
            if not ("you save" in page_src or "was" in page_src or "save" in page_src or "discount" in page_src):
                return False

        return True

    def _is_prime(self) -> bool:
        try:
            el = self.driver.find_elements(By.CSS_SELECTOR, ".a-icon-prime")
            return bool(el)
        except Exception:
            return False

    def extract_asin(self, url: str) -> str:
        try:
            if "/dp/" in url:
                return url.split("/dp/")[1].split("/")[0]
            if "/gp/product/" in url:
                return url.split("/gp/product/")[1].split("/")[0]
            m = re.search(r"/([A-Z0-9]{10})(?:[/?]|$)", url)
            if m:
                return m.group(1)
        except Exception:
            pass
        return "UNKNOWN"
