import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QFileSystemModel, QFileDialog, QDialog
from PySide6.QtCore import QThreadPool, QFile, QDir, QStandardPaths
from PySide6.QtUiTools import QUiLoader

# Custom modules
from project_manager import ProjectManager
from downloader_interfaces import DownloadWorker
from dialog_controllers import (
    LoadIpDialogController,
    LoadIrmsDialogController,
    LoadSoiDialogController,
    CompareSoiDialogController
)


class ApplicationController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.thread_pool = QThreadPool()
        self.active_irm_dialog = None  # Reference for async callbacks

        # 1. Load the UI XML
        self.load_ui()

        # 2. Find Documents folder and initialize the Project Manager
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self.base_projects_dir = QDir(docs_path).filePath("IP_Projects")
        self.project_mgr = ProjectManager(self.base_projects_dir)

        # 3. Setup models and signals
        self.setup_models()
        self.connect_signals()

    def load_ui(self):
        loader = QUiLoader()
        ui_file = QFile("UI/mainwindow.ui")
        if not ui_file.open(QFile.ReadOnly):
            print(f"Cannot open UI file: {ui_file.errorString()}")
            sys.exit(-1)

        self.window = loader.load(ui_file)
        ui_file.close()

    def setup_models(self):
        # Create a default active project so the workspace isn't empty on launch
        default_project = self.project_mgr.create_new_project()

        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath(str(default_project))

        self.window.treeView.setModel(self.file_system_model)
        self.window.treeView.setRootIndex(self.file_system_model.index(str(default_project)))

        # Hide size, type, and date columns
        self.window.treeView.setHeaderHidden(True)
        for i in range(1, 4):
            self.window.treeView.hideColumn(i)

        # Update the UI label to show the current workspace
        self.window.labelWorkspace.setText(f"Workspace: {default_project.name}")
        self.window.labelWorkspace.setToolTip(str(default_project))

        # Add the auto-generated toggle action for the log dock to the View menu
        toggle_log_action = self.window.logDockWidget.toggleViewAction()
        toggle_log_action.setText("Show Application Log")
        self.window.menuView.addAction(toggle_log_action)

    def connect_signals(self):
        self.window.actionOpenFolder.triggered.connect(self.handle_open_folder)
        self.window.actionLoadIP.triggered.connect(self.handle_load_ip)
        self.window.actionLoadIRMs.triggered.connect(self.handle_load_irms)
        self.window.actionLoadSOI.triggered.connect(self.handle_load_soi)
        self.window.actionCompareSOI.triggered.connect(self.handle_compare_soi)

    def log(self, message):
        self.window.logOutput.append(message)

    # --- Ribbon Action Handlers ---

    def handle_open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(
            self.window,
            "Select Project Folder",
            self.base_projects_dir
        )

        if folder_path:
            self.log(f"Opened project workspace: {folder_path}")

            # Tell the manager to update its internal state
            self.project_mgr.set_active_project(folder_path)

            # Update the tree view and labels
            self.window.treeView.setRootIndex(self.file_system_model.index(folder_path))
            folder_name = QDir(folder_path).dirName()
            self.window.labelWorkspace.setText(f"Workspace: {folder_name}")
            self.window.labelWorkspace.setToolTip(folder_path)

    def handle_load_ip(self):
        self.log("Opening Batch Load IP modal...")
        dialog_controller = LoadIpDialogController(self.window)

        if dialog_controller.exec() == QDialog.Accepted:
            tasks = dialog_controller.get_data()
            if not tasks:
                self.log("Warning: No valid IP data entered.")
                return

            for task in tasks:
                self.log(f"Queued IP: {task['ip']} LN: {task['ln']}")

                # 1. Physically create the folders on disk
                self.project_mgr.setup_ip_environment(task['ip'], task['ln'])

                # 2. Fire off the base IP setup worker
                self.spawn_download_task("IP_SETUP", task['ip'], task['ln'])

                # 3. Queue optional downloads
                if task['load_irms']:
                    self.spawn_download_task("IRM", task['ip'], task['ln'])
                if task['load_soi']:
                    self.spawn_download_task("SOI", task['ip'], task['ln'])

    def handle_load_irms(self):
        self.log("Opening IRM selection modal...")
        active_ips = self.project_mgr.get_loaded_ips()

        if not active_ips:
            self.log("Cannot load IRMs: No IPs found in the current project folder.")
            return

        # Pass the async callback function to the controller
        self.active_irm_dialog = LoadIrmsDialogController(active_ips, self.fetch_irm_list_for_dialog, self.window)

        if self.active_irm_dialog.exec() == QDialog.Accepted:
            data = self.active_irm_dialog.get_data()
            self.log(f"Queued IRM downloads for {data['ip_ln']}: {', '.join(data['parts'])}")

            ip_num, ln_num = data['ip_ln'].rsplit('-', 1)
            for part in data['parts']:
                self.spawn_download_task("IRM", ip_num, ln_num, part_number=part)

        # Clean up the reference when the dialog closes
        self.active_irm_dialog = None

    def fetch_irm_list_for_dialog(self, ip_ln):
        """Callback triggered by the dialog when the dropdown changes"""
        ip_num, ln_num = ip_ln.rsplit('-', 1)
        self.spawn_download_task("FETCH_IRM_LIST", ip_num, ln_num)

    def handle_load_soi(self):
        self.log("Opening SOI selection modal...")
        active_ips = self.project_mgr.get_loaded_ips()

        if not active_ips:
            self.log("Cannot load SOI: No IPs found in the current project folder.")
            return

        dialog_controller = LoadSoiDialogController(active_ips, self.window)

        if dialog_controller.exec() == QDialog.Accepted:
            selected_ip = dialog_controller.get_data()
            if selected_ip:
                self.log(f"Queued SOI download for {selected_ip}")
                ip_num, ln_num = selected_ip.rsplit('-', 1)
                self.spawn_download_task("SOI", ip_num, ln_num)

    def handle_compare_soi(self):
        self.log("Opening Compare SOI window...")
        active_ips = self.project_mgr.get_loaded_ips()

        if len(active_ips) < 2:
            self.log("Error: Need at least 2 loaded IPs to run a comparison.")
            return

        # Pass the project_mgr into the dialog so it can read the HTML files
        dialog_controller = CompareSoiDialogController(active_ips, self.project_mgr, self.window)
        dialog_controller.exec()

    # --- Threading & Network Simulation ---

    def spawn_download_task(self, task_type, ip_num, ln_num, **kwargs):
        # Calculate the absolute path where the worker should save files
        if self.project_mgr.active_project_path:
            ip_dir = self.project_mgr.active_project_path / f"{ip_num}-{ln_num}"
            kwargs['save_path'] = str(ip_dir)

        worker = DownloadWorker(task_type, ip_num, ln_num, **kwargs)
        worker.signals.log_msg.connect(self.log)
        worker.signals.finished.connect(self.on_download_finished)
        worker.signals.error.connect(self.on_download_error)

        # Connect the data_ready signal so FETCH_IRM_LIST can return the UI list
        worker.signals.data_ready.connect(self.on_worker_data_ready)

        self.thread_pool.start(worker)

    def on_worker_data_ready(self, task_type, identifier, payload):
        """Catches data payloads from background workers"""
        if task_type == "FETCH_IRM_LIST" and self.active_irm_dialog:
            current_dialog_ip = self.active_irm_dialog.dialog.comboIpLn.currentText()
            # Check if the user hasn't quickly changed the dropdown again
            if current_dialog_ip == identifier:
                self.active_irm_dialog.populate_parts(payload)

    def on_download_finished(self, identifier, status):
        self.window.statusbar.showMessage(f"Finished {identifier}", 5000)

    def on_download_error(self, identifier, error_msg):
        self.window.statusbar.showMessage(f"Error on {identifier}: {error_msg}", 5000)

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    controller = ApplicationController()
    controller.run()