# gui.py
import os
from PySide6.QtCore import QThread, Qt, Slot
from worker import ScraperWorker
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QProgressBar, QTextEdit, QMessageBox

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem, QTabWidget, QLabel,
    QScrollArea, QSizePolicy, QFileDialog
)

import requests

class ModernTrackerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amazon Price Tracker")
        self.setGeometry(100, 50, 1400, 900)
        self.is_dark = False

        # Thread refs
        self.thread = None
        self.worker = None

        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        sidebar_widget = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(2, 2, 2, 2)
        sidebar_layout.setSpacing(5)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        sidebar_layout.addWidget(self.tabs)

        # General tab
        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setAlignment(Qt.AlignTop)

        self.image_dir_input = QLineEdit()
        self.image_dir_btn = QPushButton("Select Image Folder")
        self.image_dir_btn.clicked.connect(self.select_image_folder)
        general_layout.addWidget(self.labeled_widget("Image Folder:", self.image_dir_input))
        general_layout.addWidget(self.image_dir_btn)

        self.product_input = QLineEdit()
        self.asin_input = QLineEdit()

        self.domain_input = QComboBox()
        self.domain_input.addItems([
            "US (.com)",
            "DE (.de)",
            "FR (.fr)",
            "UK (.co.uk)",
            "IT (.it)",
            "ES (.es)"
        ])

        self.proxy_textbox = QTextEdit()
        self.proxy_textbox.setPlaceholderText(
            "Enter proxies here (one per line):\n"
            "http://user:pass@ip:port\n"
            "http://ip:port"
        )
        self.proxy_textbox.setFixedHeight(100)
        general_layout.addWidget(self.labeled_widget("Proxy List (Rotating):", self.proxy_textbox))

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter product URL (optional)")
        general_layout.addWidget(self.labeled_widget("Product URL:", self.url_input))

        self.country_input = QComboBox()
        self.country_input.addItems(["US", "DE", "UK", "FR", "IT", "ES"])

        self.currency_input = QComboBox()
        self.currency_input.addItems(["$", "€", "£"])

        self.out_dir_input = QLineEdit()
        self.out_dir_btn = QPushButton("Select Folder")
        self.out_dir_btn.clicked.connect(self.select_folder)

        self.export_format_input = QComboBox()
        self.export_format_input.addItems(["csv", "xls", "xlsx", "json"])

        general_layout.addWidget(self.labeled_widget("Product Search:", self.product_input))
        general_layout.addWidget(self.labeled_widget("ASINs (space separated):", self.asin_input))
        general_layout.addWidget(self.labeled_widget("Amazon Domain:", self.domain_input))
        general_layout.addWidget(self.labeled_widget("Country:", self.country_input))
        general_layout.addWidget(self.labeled_widget("Currency:", self.currency_input))
        general_layout.addWidget(self.labeled_widget("Output Folder:", self.out_dir_input))
        general_layout.addWidget(self.out_dir_btn)
        general_layout.addWidget(self.labeled_widget("Export Format:", self.export_format_input))

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.stop_btn = QPushButton("Stop Scraping")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scraping)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(150)

        self.download_images_checkbox = QCheckBox("Download Images")
        general_layout.addWidget(self.download_images_checkbox)

        general_layout.addWidget(self.progress_bar)
        general_layout.addWidget(self.stop_btn)
        general_layout.addWidget(self.log_box)

        self.tabs.addTab(general_tab, "General")

        # PRICE TAB
        price_tab = QWidget()
        price_layout = QVBoxLayout(price_tab)
        price_layout.setAlignment(Qt.AlignTop)
        self.min_price_input = QDoubleSpinBox()
        self.min_price_input.setMaximum(999999)
        self.max_price_input = QDoubleSpinBox()
        self.max_price_input.setMaximum(999999)
        self.max_price_input.setValue(9999)
        price_layout.addWidget(self.labeled_widget("Min Price:", self.min_price_input))
        price_layout.addWidget(self.labeled_widget("Max Price:", self.max_price_input))
        self.tabs.addTab(price_tab, "Price")

        # RATING
        rating_tab = QWidget()
        rating_layout = QVBoxLayout(rating_tab)
        rating_layout.setAlignment(Qt.AlignTop)
        self.min_rating_input = QDoubleSpinBox()
        self.min_rating_input.setRange(0, 5)
        self.min_rating_input.setSingleStep(0.1)
        self.max_rating_input = QDoubleSpinBox()
        self.max_rating_input.setRange(0, 5)
        self.max_rating_input.setValue(5)
        self.min_reviews_input = QSpinBox()
        self.min_reviews_input.setMaximum(9999999)
        self.max_reviews_input = QSpinBox()
        self.max_reviews_input.setMaximum(9999999)
        self.max_reviews_input.setValue(9999999)
        rating_layout.addWidget(self.labeled_widget("Min Rating:", self.min_rating_input))
        rating_layout.addWidget(self.labeled_widget("Max Rating:", self.max_rating_input))
        rating_layout.addWidget(self.labeled_widget("Min Reviews:", self.min_reviews_input))
        rating_layout.addWidget(self.labeled_widget("Max Reviews:", self.max_reviews_input))
        self.tabs.addTab(rating_tab, "Rating/Reviews")

        # BRAND
        brand_tab = QWidget()
        brand_layout = QVBoxLayout(brand_tab)
        brand_layout.setAlignment(Qt.AlignTop)
        self.brand_input = QLineEdit()
        self.brands_input = QLineEdit()
        self.category_input = QLineEdit()
        brand_layout.addWidget(self.labeled_widget("Brand (single):", self.brand_input))
        brand_layout.addWidget(self.labeled_widget("Brands (space sep.):", self.brands_input))
        brand_layout.addWidget(self.labeled_widget("Category Node:", self.category_input))
        self.tabs.addTab(brand_tab, "Brand/Category")

        # SELLER
        seller_tab = QWidget()
        seller_layout = QVBoxLayout(seller_tab)
        seller_layout.setAlignment(Qt.AlignTop)
        self.condition_input = QComboBox()
        self.condition_input.addItems(["Any", "new", "used", "refurbished"])
        self.seller_type_input = QComboBox()
        self.seller_type_input.addItems(["Any", "amazon", "fba", "fbm"])
        self.discount_only = QCheckBox("Discount Only")
        self.prime_only = QCheckBox("Prime Only")
        self.in_stock_only = QCheckBox("In Stock Only")
        seller_layout.addWidget(self.labeled_widget("Condition:", self.condition_input))
        seller_layout.addWidget(self.labeled_widget("Seller Type:", self.seller_type_input))
        seller_layout.addWidget(self.discount_only)
        seller_layout.addWidget(self.prime_only)
        seller_layout.addWidget(self.in_stock_only)
        self.tabs.addTab(seller_tab, "Seller")

        # KEYWORDS
        keywords_tab = QWidget()
        keywords_layout = QVBoxLayout(keywords_tab)
        keywords_layout.setAlignment(Qt.AlignTop)
        self.include_keywords_input = QLineEdit()
        self.exclude_keywords_input = QLineEdit()
        keywords_layout.addWidget(self.labeled_widget("Include Keywords:", self.include_keywords_input))
        keywords_layout.addWidget(self.labeled_widget("Exclude Keywords:", self.exclude_keywords_input))
        self.tabs.addTab(keywords_tab, "Keywords")

        # BSR / Pages
        bsr_tab = QWidget()
        bsr_layout = QVBoxLayout(bsr_tab)
        bsr_layout.setAlignment(Qt.AlignTop)
        self.bsr_min_input = QSpinBox()
        self.bsr_min_input.setMaximum(9999999)
        self.bsr_max_input = QSpinBox()
        self.bsr_max_input.setMaximum(9999999)
        self.bsr_max_input.setValue(9999999)
        self.max_pages_input = QSpinBox()
        self.max_pages_input.setMaximum(100)
        self.max_pages_input.setValue(5)
        self.pages_per_proxy_input = QSpinBox()
        self.pages_per_proxy_input.setMaximum(100)
        self.pages_per_proxy_input.setValue(2)
        bsr_layout.addWidget(self.labeled_widget("BSR Min:", self.bsr_min_input))
        bsr_layout.addWidget(self.labeled_widget("BSR Max:", self.bsr_max_input))
        bsr_layout.addWidget(self.labeled_widget("Max Pages:", self.max_pages_input))
        bsr_layout.addWidget(self.labeled_widget("Pages per Proxy:", self.pages_per_proxy_input))
        self.tabs.addTab(bsr_tab, "BSR/Pages")

        # Advanced
        adv_tab = QWidget()
        adv_layout = QVBoxLayout(adv_tab)
        adv_layout.setAlignment(Qt.AlignTop)
        self.use_uc = QCheckBox("Use UC")
        self.headless = QCheckBox("Headless Mode")
        adv_layout.addWidget(self.use_uc)
        adv_layout.addWidget(self.headless)
        self.tabs.addTab(adv_tab, "Advanced")

        # Buttons
        self.track_btn = QPushButton("Track")
        self.track_btn.clicked.connect(self.track_price)
        sidebar_layout.addWidget(self.track_btn)

        self.theme_btn = QPushButton("Toggle Dark/Light Mode")
        self.theme_btn.clicked.connect(self.switch_theme)
        sidebar_layout.addWidget(self.theme_btn)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(sidebar_widget)
        main_layout.addWidget(scroll, 1)

        # Result table
        self.table = QTableWidget()
        self.table.setColumnCount(20)
        self.table.setHorizontalHeaderLabels([
            "Title", "ASIN", "Price", "Rating", "Reviews", "Prime", "Stock", "URL", "Image URL",
            "Brand", "Condition", "Seller Type", "Discount", "Category Node", "BSR", "Currency",
            "Country", "Include Keywords", "Exclude Keywords", "Other"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.table, 2)

        self.apply_styles()

    def load_proxies(self):
        raw = self.proxy_textbox.toPlainText().strip().split("\n")
        proxies = [p.strip() for p in raw if p.strip()]

        if not proxies:
            self.write_log("⚠ No proxies loaded — using direct connection.")
        else:
            self.write_log(f"Loaded {len(proxies)} proxies.")

        return proxies

    def stop_scraping(self):
        if self.worker is not None:
            try:
                self.worker.stop()
                self.stop_btn.setEnabled(False)
            except Exception:
                pass

    def labeled_widget(self, label_text, widget):
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.addWidget(QLabel(label_text))
        layout.addWidget(widget)
        return w

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if folder:
            self.out_dir_input.setText(folder)

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f5f5; }
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 4px; border-radius: 5px; }
            QPushButton { background-color: #0078d7; color: white; border-radius: 5px; padding: 6px; }
            QPushButton:hover { background-color: #005a9e; }
            QTabWidget::pane { border: 1px solid #ccc; border-radius: 5px; }
        """)

    def switch_theme(self):
        self.is_dark = not self.is_dark
        if self.is_dark:
            self.setStyleSheet("""
                QMainWindow { background-color: #2e2e2e; color: #f0f0f0; }
                QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #3e3e3e; color: #f0f0f0; }
                QPushButton { background-color: #555555; color: #f0f0f0; }
                QTabWidget::pane { border: 1px solid #555; }
            """)
        else:
            self.apply_styles()

    def track_price(self):
        proxies = self.load_proxies()

        search_term = self.product_input.text().strip()
        asin_text = self.asin_input.text().strip()
        asin_list = asin_text.split() if asin_text else None

        domain_map = {
            "US (.com)": "https://www.amazon.com",
            "DE (.de)": "https://www.amazon.de",
            "FR (.fr)": "https://www.amazon.fr",
            "UK (.co.uk)": "https://www.amazon.co.uk",
            "IT (.it)": "https://www.amazon.it",
            "ES (.es)": "https://www.amazon.es"
        }
        selected_domain_label = self.domain_input.currentText()
        base_url = domain_map.get(selected_domain_label, "https://www.amazon.com")

        country = self.country_input.currentText()
        currency = self.currency_input.currentText()
        image_dir = self.image_dir_input.text().strip() or None

        filters = {
            "min": self.min_price_input.value(),
            "max": self.max_price_input.value(),
            "min_rating": float(self.min_rating_input.value()),
            "max_rating": float(self.max_rating_input.value()),
            "min_reviews": int(self.min_reviews_input.value()),
            "max_reviews": int(self.max_reviews_input.value()),
            "prime_only": self.prime_only.isChecked(),
            "in_stock_only": self.in_stock_only.isChecked(),
            "brand": self.brand_input.text() or None,
            "brands": self.brands_input.text().split() if self.brands_input.text() else [],
            "category_node": self.category_input.text().strip() or None,
            "condition": self.condition_input.currentText(),
            "discount_only": self.discount_only.isChecked(),
            "seller_type": self.seller_type_input.currentText(),
            "bsr_min": self.bsr_min_input.value(),
            "bsr_max": self.bsr_max_input.value(),
            "include_keywords": self.include_keywords_input.text().split() if self.include_keywords_input.text() else [],
            "exclude_keywords": self.exclude_keywords_input.text().split() if self.exclude_keywords_input.text() else [],
            "max_pages": self.max_pages_input.value(),
            "pages_per_proxy": self.pages_per_proxy_input.value(),
            "country": country,
            "currency": currency,
            "use_uc": self.use_uc.isChecked(),
            "headless": self.headless.isChecked(),
            "base_url": base_url,
        }

        self.table.setRowCount(0)

        self.worker = ScraperWorker(
            search_term=search_term,
            asin_list=asin_list,
            filters=filters,
            proxies=proxies,
            download_images=self.download_images_checkbox.isChecked(),
            image_dir=image_dir
        )

        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.write_log)
        self.worker.partial.connect(self.add_live_row)
        self.worker.stopped.connect(self.scraping_stopped)
        self.worker.finished.connect(self.scraping_done)
        self.worker.error.connect(self.thread_error)

        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()
        self.stop_btn.setEnabled(True)

    def scraping_done(self, products):
        self.write_log(f"[✔] Scraping finished. Total products: {len(products)}")
        try:
            self.populate_table(products)
        finally:
            self.stop_btn.setEnabled(False)
            self.progress_bar.setValue(100)

    def thread_error(self, msg):
        QMessageBox.critical(self, "Error", msg)
        print(msg)
        self.stop_btn.setEnabled(False)

    def download_images(self, products):
        folder = self.image_dir_input.text().strip() or "images"
        os.makedirs(folder, exist_ok=True)

        for item in products:
            img_url = item.get("image_url") or item.get("image")
            asin = item.get("asin", "unknown")

            if not img_url:
                self.write_log(f"[❌] Product {asin} has no image URL")
                continue

            try:
                ext = img_url.split('.')[-1].split('?')[0]
                if len(ext) > 5 or '/' in ext:
                    ext = "jpg"

                filename = os.path.join(folder, f"{asin}.{ext}")

                response = requests.get(img_url, timeout=12)
                if response.status_code == 200:
                    with open(filename, "wb") as f:
                        f.write(response.content)
                    self.write_log(f"[✔] Downloaded {filename}")
                else:
                    self.write_log(f"[❌] Failed: HTTP {response.status_code} — {img_url}")

            except Exception as e:
                self.write_log(f"[❌] Error downloading {img_url}: {e}")

    def update_progress(self, value):
        try:
            self.progress_bar.setValue(int(value))
        except Exception:
            pass

    def write_log(self, msg):
        self.log_box.append(msg)

    def add_live_row(self, product):
        row = self.table.rowCount()
        self.table.insertRow(row)

        col = 0
        for key in product.keys():
            try:
                if key in ("image", "image_url"):
                    pix = QPixmap(product.get(key) or "")
                    if not pix.isNull():
                        item = QTableWidgetItem()
                        item.setData(Qt.DecorationRole, pix.scaled(80, 80))
                        self.table.setItem(row, col, item)
                    else:
                        self.table.setItem(row, col, QTableWidgetItem(str(product.get(key, ""))))
                else:
                    self.table.setItem(row, col, QTableWidgetItem(str(product.get(key, ""))))
            except Exception:
                try:
                    self.table.setItem(row, col, QTableWidgetItem(str(product.get(key, ""))))
                except Exception:
                    pass
            col += 1

    def scraping_stopped(self):
        self.write_log("[⚠] Scraping stopped.")
        self.progress_bar.setValue(0)
        self.stop_btn.setEnabled(False)

    def populate_table(self, products):
        self.table.setRowCount(len(products))
        for row, p in enumerate(products):
            self.table.setItem(row, 0, QTableWidgetItem(p.get("title", "")))
            self.table.setItem(row, 1, QTableWidgetItem(p.get("asin", "")))
            self.table.setItem(row, 2, QTableWidgetItem(str(p.get("price", ""))))
            self.table.setItem(row, 3, QTableWidgetItem(str(p.get("rating", ""))))
            self.table.setItem(row, 4, QTableWidgetItem(str(p.get("reviews", ""))))
            self.table.setItem(row, 5, QTableWidgetItem(str(p.get("prime", ""))))
            self.table.setItem(row, 6, QTableWidgetItem(str(p.get("stock", ""))))
            self.table.setItem(row, 7, QTableWidgetItem(p.get("url", "")))
            self.table.setItem(row, 8, QTableWidgetItem(p.get("image_url", "")))
            self.table.setItem(row, 9, QTableWidgetItem(p.get("brand", "")))
            self.table.setItem(row, 10, QTableWidgetItem(p.get("condition", "")))
            self.table.setItem(row, 11, QTableWidgetItem(p.get("seller_type", "")))
            self.table.setItem(row, 12, QTableWidgetItem(str(p.get("discount", ""))))
            self.table.setItem(row, 13, QTableWidgetItem(p.get("category_node", "")))
            self.table.setItem(row, 14, QTableWidgetItem(str(p.get("bsr", ""))))
            self.table.setItem(row, 15, QTableWidgetItem(p.get("currency", "")))
            self.table.setItem(row, 16, QTableWidgetItem(p.get("country", "")))
            self.table.setItem(row, 17, QTableWidgetItem(", ".join(p.get("include_keywords", []))))
            self.table.setItem(row, 18, QTableWidgetItem(", ".join(p.get("exclude_keywords", []))))
            self.table.setItem(row, 19, QTableWidgetItem(str(p.get("other", ""))))

    def select_image_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Image Folder")
        if folder:
            self.image_dir_input.setText(folder)


if __name__ == "__main__":
    app = QApplication([])
    window = ModernTrackerGUI()
    window.show()
    app.exec()
