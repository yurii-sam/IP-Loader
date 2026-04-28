import time
from pathlib import Path
from PySide6.QtCore import QRunnable, QObject, Signal, Slot

# Import your Velocity client
# Assuming it's in a file named velocity.py
from velocity import VelocityClient


class WorkerSignals(QObject):
    finished = Signal(str, str)
    data_ready = Signal(str, str, object)
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
            save_path = Path(self.kwargs.get("save_path", ""))

            if self.task_type == "FETCH_IRM_LIST":
                # Implementation remains...
                pass

            elif self.task_type == "IP_SETUP":
                # Implementation remains...
                pass

            elif self.task_type == "SOI":
                self.signals.log_msg.emit(f"Connecting to Velocity for {identifier}...")

                # Retrieve the SSO session passed from main.py
                sso_session = self.kwargs.get("sso_session")
                if not sso_session:
                    raise ValueError("No authenticated SSO session provided.")

                # Instantiate the client and run the extraction
                client = VelocityClient(sso_session)

                # Execute the search and print payload
                # Note: You may need to slightly adjust VelocityClient.process_order
                # so it saves the file directly into the provided save_path
                success = client.process_order(self.ip_number, self.line_number, target_dir=str(save_path))

                if not success:
                    raise RuntimeError("Velocity server rejected the payload or redirect failed.")

            elif self.task_type == "IRM":
                # Implementation remains...
                pass

            self.signals.log_msg.emit(f"Successfully finished {self.task_type} for {identifier}")
            self.signals.finished.emit(identifier, "Success")

        except Exception as e:
            self.signals.error.emit(identifier, str(e))
            self.signals.log_msg.emit(f"Error on {identifier}: {str(e)}")