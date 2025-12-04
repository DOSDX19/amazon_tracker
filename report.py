# report.py
import os
import csv
import json
from typing import List, Dict, Any

try:
    import pandas as pd
    _HAS_PANDAS = True
except Exception:
    _HAS_PANDAS = False

class Report:
    def __init__(self, file_name: str, directory: str, currency, filters: Dict[str, Any], base_url: str, data: List[Dict[str, Any]], export_format: str = "csv"):
        self.file_name = file_name
        self.directory = directory
        self.currency = currency
        self.filters = filters or {}
        self.base_url = base_url
        self.data = data or []
        self.export_format = (export_format or "csv").lower()
        os.makedirs(self.directory, exist_ok=True)
        self._export()

    def _export(self):
        if self.export_format == "csv":
            self._to_csv()
        elif self.export_format in ("xls", "xlsx"):
            self._to_excel()
        elif self.export_format == "json":
            self._to_json()
        elif self.export_format == "txt":
            self._to_txt()
        elif self.export_format == "html":
            self._to_html()
        else:
            raise ValueError(f"Unsupported export format: {self.export_format}")

    def _to_csv(self):
        path = os.path.join(self.directory, f"{self.file_name}.csv")
        if not self.data:
            # write headerless empty file
            open(path, "w", encoding="utf-8").close()
            return
        # ensure consistent ordering of columns — use keys of first item
        headers = list(self.data[0].keys())
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in self.data:
                writer.writerow([row.get(h, "") for h in headers])

    def _to_excel(self):
        if not _HAS_PANDAS:
            raise RuntimeError("pandas required for Excel export")
        path = os.path.join(self.directory, f"{self.file_name}.xlsx")
        df = pd.DataFrame(self.data)
        df.to_excel(path, index=False)

    def _to_json(self):
        path = os.path.join(self.directory, f"{self.file_name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def _to_txt(self):
        path = os.path.join(self.directory, f"{self.file_name}.txt")
        with open(path, "w", encoding="utf-8") as f:
            for item in self.data:
                f.write(str(item) + "\n")

    def _to_html(self):
        if not _HAS_PANDAS:
            raise RuntimeError("pandas required for HTML export")
        path = os.path.join(self.directory, f"{self.file_name}.html")
        df = pd.DataFrame(self.data)
        df.to_html(path, index=False)
