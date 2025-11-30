# report.py
class Report:
    def __init__(self, file_name, directory, currency, filters, base_url, data, export_format="csv"):
        self.file_name = file_name
        self.directory = directory
        self.currency = currency
        self.filters = filters
        self.base_url = base_url
        self.data = data or []
        self.export_format = export_format.lower()

        self._ensure_directory()
        self._export()

    def _ensure_directory(self):
        import os
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)

    def _export(self):
        if self.export_format == "csv":
            self._to_csv()
        elif self.export_format == "xlsx":
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
        import csv, os
        path = os.path.join(self.directory, f"{self.file_name}.csv")
        if not self.data:
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("")
            return
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # ensure keys order stable
            first = list(self.data[0].keys())
            writer.writerow(first)
            for row in self.data:
                writer.writerow([row.get(k, "") for k in first])

    def _to_excel(self):
        import pandas as pd, os
        df = pd.DataFrame(self.data)
        df.to_excel(os.path.join(self.directory, f"{self.file_name}.xlsx"), index=False)

    def _to_json(self):
        import json, os
        with open(os.path.join(self.directory, f"{self.file_name}.json"), "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def _to_txt(self):
        import os
        path = os.path.join(self.directory, f"{self.file_name}.txt")
        with open(path, "w", encoding="utf-8") as f:
            for item in self.data:
                f.write(str(item) + "\n")

    def _to_html(self):
        import pandas as pd, os
        df = pd.DataFrame(self.data)
        df.to_html(os.path.join(self.directory, f"{self.file_name}.html"), index=False)
