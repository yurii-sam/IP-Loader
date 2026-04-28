import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QDialog, QMessageBox
)
from PySide6.QtCore import (
    QThreadPool, QFile, QDir, QStandardPaths, QFileInfo
)
from PySide6.QtGui import QPalette
from PySide6.QtUiTools import QUiLoader

import qtawesome as qta

# Custom modules
from .core.project_manager import ProjectManager
from .core.downloader import DownloadWorker
from .ui.dialogs import (
    LoadIpDialogController,
    LoadIrmsDialogController,
    LoadSoiDialogController,
    CompareSoiDialogController
)
from .ui.preview_panel import PreviewPanel
from .ui.tree_manager import TreeManager


class ApplicationController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.thread_pool = QThreadPool()
        self.active_irm_dialog = None

        # 1. Load the UI XML
        self.load_ui()

        # 2. Setup standard icons
        self.setup_icons()

        # 3. Find Documents folder and initialize the Project Manager
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self.base_projects_dir = QDir(docs_path).filePath("IP_Projects")
        self.project_mgr = ProjectManager(self.base_projects_dir)

        # 4. Initialize Sub-Managers
        self.preview_panel = PreviewPanel(self.window, self.log)
        self.tree_manager = TreeManager(self.window, self.project_mgr, self.log, self.preview_panel)

        # 5. Setup models and signals
        self.setup_models()
        self.connect_signals()

    def load_ui(self):
        loader = QUiLoader()
        ui_path = Path(__file__).parent / "ui" / "views" / "mainwindow.ui"
        ui_file = QFile(str(ui_path))
        if not ui_file.open(QFile.ReadOnly):
            print(f"Cannot open UI file: {ui_file.errorString()}")
            sys.exit(-1)

        self.window = loader.load(ui_file)
        ui_file.close()

    def setup_icons(self):
        palette = self.app.palette()
        is_dark_mode = palette.color(QPalette.WindowText).lightness() > palette.color(QPalette.Window).lightness()
        icon_color = '#FFFFFF' if is_dark_mode else '#333333'

        self.window.actionOpenFolder.setIcon(qta.icon('ph.folder-open', color=icon_color))
        self.window.actionLoadIP.setIcon(qta.icon('ph.folder-plus', color=icon_color))
        self.window.actionLoadIRMs.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionLoadSOI.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionCompareSOI.setIcon(qta.icon('ph.git-diff', color=icon_color))

    def setup_models(self):
        default_project = self.project_mgr.create_new_project()
        self.tree_manager.setup_tree(default_project)

        # Update the UI label to show the current workspace
        self.window.labelWorkspace.setText(f"Workspace: {default_project.name}")
        self.window.labelWorkspace.setToolTip(str(default_project))

        # Add the auto-generated toggle action for the log dock to the View menu
        toggle_log_action = self.window.logDockWidget.toggleViewAction()
        toggle_log_action.setText("Show Application Log")
        self.window.menuView.addAction(toggle_log_action)

        # Force the splitter to give the preview pane the lion's share of the window
        self.window.mainSplitter.setSizes([250, 950])

    def connect_signals(self):
        self.window.actionOpenFolder.triggered.connect(self.handle_open_folder)
        self.window.actionLoadIP.triggered.connect(self.handle_load_ip)
        self.window.actionLoadIRMs.triggered.connect(self.handle_load_irms)
        self.window.actionLoadSOI.triggered.connect(self.handle_load_soi)
        self.window.actionCompareSOI.triggered.connect(self.handle_compare_soi)
        
        self.window.treeView.clicked.connect(lambda idx: self.preview_panel.handle_file_selection(self.tree_manager.file_system_model.filePath(idx)))
        self.window.treeView.customContextMenuRequested.connect(self.tree_manager.show_tree_context_menu)
        
        self.window.btnOpenPdf.clicked.connect(self.preview_panel.open_external_pdf)

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
            self.project_mgr.set_active_project(folder_path)
            self.tree_manager.update_root(folder_path)
            
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
                self.project_mgr.setup_ip_environment(task['ip'], task['ln'])
                self.spawn_download_task("IP_SETUP", task['ip'], task['ln'])

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

        self.active_irm_dialog = LoadIrmsDialogController(active_ips, self.fetch_irms_for_dialog, self.window)
        if self.active_irm_dialog.exec() == QDialog.Accepted:
            data = self.active_irm_dialog.get_data()
            ip_ln = data["ip_ln"]
            parts = data["parts"]

            ip, ln = ip_ln.split("-")
            self.log(f"Queued IRMs for {ip_ln}: {', '.join(parts)}")
            self.spawn_download_task("IRM", ip, ln, parts=parts)

        self.active_irm_dialog = None

    def fetch_irms_for_dialog(self, ip_ln):
        ip, ln = ip_ln.split("-")
        self.spawn_download_task("FETCH_IRM_LIST", ip, ln)

    def handle_load_soi(self):
        active_ips = self.project_mgr.get_loaded_ips()
        dialog = LoadSoiDialogController(active_ips, self.window)

        if dialog.exec() == QDialog.Accepted:
            ip_ln = dialog.get_data()
            ip, ln = ip_ln.split("-")
            self.log(f"Queued SOI for {ip_ln}")
            self.spawn_download_task("SOI", ip, ln)

    def handle_compare_soi(self):
        active_ips = self.project_mgr.get_loaded_ips()
        if len(active_ips) < 2:
            QMessageBox.information(self.window, "Not Enough Data", "You need at least two loaded IPs to run a comparison.")
            return

        dialog = CompareSoiDialogController(active_ips, self.project_mgr, self.window)
        dialog.exec()

    # --- Background Worker Management ---

    def spawn_download_task(self, task_type, ip, ln, **kwargs):
        save_path = self.project_mgr.active_project_path / f"{ip}-{ln}"
        worker = DownloadWorker(task_type, ip, ln, save_path=save_path, **kwargs)

        worker.signals.log_msg.connect(self.log)
        worker.signals.finished.connect(self.on_download_finished)
        worker.signals.error.connect(self.on_download_error)
        worker.signals.data_ready.connect(self.on_worker_data_ready)

        self.thread_pool.start(worker)

    def on_worker_data_ready(self, identifier, task_type, payload):
        if task_type == "FETCH_IRM_LIST" and self.active_irm_dialog:
            current_dialog_ip = self.active_irm_dialog.dialog.comboIpLn.currentText()
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
