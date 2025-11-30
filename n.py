# # def track_price(self):

#     # LOAD PROXIES
#     proxies = self.load_proxies()

#     # READ BASIC INPUTS
#     search_term = self.product_input.text().strip()
#     asin_text = self.asin_input.text().strip()
#     asin_list = asin_text.split() if asin_text else None
#     domain = self.domain_input.currentText().split("(")[1].replace(")", "")
#     country = self.country_input.currentText()
#     currency = self.currency_input.currentText()
#     image_dir = self.image_dir_input.text().strip()

#     # FIXED FILTERS
#     filters = {
#         "min": self.min_price_input.value(),
#         "max": self.max_price_input.value(),
#         "min_rating": float(self.min_rating_input.value()),
#         "max_rating": float(self.max_rating_input.value()),
#         "min_reviews": int(self.min_reviews_input.value()),
#         "max_reviews": int(self.max_reviews_input.value()),
#         "prime_only": self.prime_only.isChecked(),
#         "in_stock_only": self.in_stock_only.isChecked(),
#         "brand": self.brand_input.text() or None,
#         "brands": self.brands_input.text().split(),
#         "category_node": self.category_input.text().strip() or None,
#         "condition": self.condition_input.currentText(),
#         "discount_only": self.discount_only.isChecked(),
#         "seller_type": self.seller_type_input.currentText(),
#         "bsr_min": self.bsr_min_input.value(),
#         "bsr_max": self.bsr_max_input.value(),
#         "include_keywords": self.include_keywords_input.text().split(),
#         "exclude_keywords": self.exclude_keywords_input.text().split(),
#         "max_pages": self.max_pages_input.value(),
#         "pages_per_proxy": self.pages_per_proxy_input.value(),
#         "country": country,
#         "currency": currency,
#         "use_uc": self.use_uc.isChecked(),
#         "headless": self.headless.isChecked(),
#     }

#     # CREATE SCRAPER WORKER (CORRECT ARGUMENTS)
#     self.worker = ScraperWorker(
#         search_term=search_term,
#         asin_list=asin_list,
#         filters=filters,
#         proxies=proxies,
#         download_images=self.download_images.isChecked() if hasattr(self, "download_images") else False,
#         image_dir=image_dir
#     )

#     # SETUP THREAD
#     self.thread = QThread()
#     self.worker.moveToThread(self.thread)

#     # CONNECT SIGNALS
#     self.thread.started.connect(self.worker.run)
#     self.worker.progress.connect(self.update_progress)
#     self.worker.log.connect(self.write_log)
#     self.worker.partial.connect(self.add_live_row)
#     self.worker.stopped.connect(self.scraping_stopped)
#     self.worker.finished.connect(self.scraping_done)
#     self.worker.error.connect(self.thread_error)

#     # CLEANUP
#     self.worker.finished.connect(self.worker.deleteLater)
#     self.thread.finished.connect(self.thread.deleteLater)

#     # START
#     self.thread.start()
#     self.stop_btn.setEnabled(True)
