import time
from pathlib import Path
from PySide6.QtCore import QRunnable, QObject, Signal, Slot


class WorkerSignals(QObject):
    finished = Signal(str, str)  # identifier, status
    data_ready = Signal(str, str, object)  # task_type, identifier, payload
    error = Signal(str, str)
    log_msg = Signal(str)


class DownloadWorker(QRunnable):
    def __init__(self, task_type, ip_number, line_number, **kwargs):
        super().__init__()
        self.task_type = task_type
        self.ip_number = ip_number
        self.line_number = line_number
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        identifier = f"{self.ip_number}-{self.line_number}"
        self.signals.log_msg.emit(f"Starting {self.task_type} for {identifier}...")

        try:
            # Simulate a network delay for the UI
            time.sleep(1.5)

            # The target directory passed from main.py
            save_path = Path(self.kwargs.get("save_path", ""))

            if self.task_type == "FETCH_IRM_LIST":
                # TODO: Replace with requests.get() to your internal API
                # This doesn't save a file, it just returns data to the UI.
                mock_parts = [
                    f"IRM-PART-{self.line_number}001",
                    f"IRM-PART-{self.line_number}002",
                    f"IRM-PART-{self.line_number}003"
                ]
                self.signals.data_ready.emit(self.task_type, identifier, mock_parts)
                return

            elif self.task_type == "IP_SETUP":
                # TODO: Fetch top-level metadata or Parts.html
                # Example: response = requests.get(f"url/parts/{self.ip_number}")
                parts_file = save_path / "Parts.html"
                if save_path.exists():
                    with open(parts_file, "w", encoding="utf-8") as f:
                        f.write(f"<html><body><h1>Parts List for {identifier}</h1></body></html>")

            elif self.task_type == "SOI":
                # TODO: Fetch the SOI Print
                soi_file = save_path / "SOI.html"
                if save_path.exists():
                    with open(soi_file, "w", encoding="utf-8") as f:
                        f.write(
                            f"<html>\n<body>\n<h1>SOI Print: {identifier}</h1>\n<p>Date: 2026-04-27</p>\n<p>Operation 10: Mock text for diffing.</p>\n</body>\n</html>")

            elif self.task_type == "IRM":
                # TODO: Fetch the 3D PDF binary
                part_number = self.kwargs.get("part_number", "UNKNOWN")
                irm_file = save_path / "IRMs" / f"{part_number}.pdf"
                if save_path.exists():
                    with open(irm_file, "wb") as f:
                        # Write raw bytes for PDFs
                        f.write(b"%PDF-1.4\n%Mock PDF binary data")

            self.signals.log_msg.emit(f"Successfully finished {self.task_type} for {identifier}")
            self.signals.finished.emit(identifier, "Success")

        except Exception as e:
            self.signals.error.emit(identifier, str(e))
            self.signals.log_msg.emit(f"Error on {identifier}: {str(e)}")