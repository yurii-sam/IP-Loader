import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QDialog, QMessageBox, QWidget, QSizePolicy
)
from PySide6.QtCore import (
    QThreadPool, QFile, QDir, QStandardPaths, QFileInfo, Qt
)
from PySide6.QtGui import QPalette, QAction
from PySide6.QtUiTools import QUiLoader

import qtawesome as qta

# Custom modules
from .core.config_manager import ConfigManager
from .core.project_manager import ProjectManager
from .core.downloader import DownloadWorker
from .ui.dialogs import (
    LoadIpDialogController,
    LoadIrmsDialogController,
    LoadSoiDialogController,
    CompareSoiDialogController,
    SettingsDialogController
)
from .ui.dialogs.new_project import NewProjectDialog
from .ui.preview_panel import PreviewPanel
from .ui.tree_manager import TreeManager


class ApplicationController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        # Store original style to restore it if needed
        self.original_style = self.app.style().objectName()
        
        self.config_mgr = ConfigManager()
        self.thread_pool = QThreadPool()
        self.active_irm_dialog = None

        # 1. Load the UI XML
        self.load_ui()

        # Apply theme
        self.apply_theme(self.config_mgr.get("theme"))

        # 2. Setup standard icons and actions
        self.setup_icons()

        # 3. Initialize the Project Manager with config path
        self.base_projects_dir = self.config_mgr.get("projects_folder")
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

        # Create or update New Project action (leftmost)
        if not hasattr(self, 'actionNewProject'):
            self.actionNewProject = QAction(qta.icon('ph.plus-circle', color=icon_color), "New Project", self.window)
            self.window.mainToolBar.insertAction(self.window.actionOpenFolder, self.actionNewProject)
        else:
            self.actionNewProject.setIcon(qta.icon('ph.plus-circle', color=icon_color))

        self.window.actionOpenFolder.setIcon(qta.icon('ph.folder-open', color=icon_color))
        self.window.actionLoadIP.setIcon(qta.icon('ph.folder-plus', color=icon_color))
        self.window.actionLoadIRMs.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionLoadSOI.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionCompareSOI.setIcon(qta.icon('ph.git-diff', color=icon_color))

        # Create or update Settings action (rightmost)
        if not hasattr(self, 'actionSettings'):
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            self.window.mainToolBar.addWidget(spacer)

            self.actionSettings = QAction(qta.icon('ph.gear', color=icon_color), "Settings", self.window)
            self.window.mainToolBar.addAction(self.actionSettings)
        else:
            self.actionSettings.setIcon(qta.icon('ph.gear', color=icon_color))

    def setup_models(self):
        last_project = self.config_mgr.get("last_project_path")
        active_project = None
        
        if last_project and Path(last_project).exists():
            if self.project_mgr.set_active_project(last_project):
                active_project = Path(last_project)
        
        if not active_project:
            # If no last project, don't create a new one automatically anymore as per request
            # But we need something to show in the tree. 
            # The issue says "make the project folder creation manual" and "save last opened Project and start the app from there"
            # If there's no last project, we might want to just show the base dir or nothing.
            # I'll show the base projects dir if it exists.
            active_project = Path(self.base_projects_dir)
            active_project.mkdir(parents=True, exist_ok=True)
            self.project_mgr.set_active_project(active_project)

        self.tree_manager.setup_tree(active_project)

        # Update the UI label to show the current workspace
        self.window.labelWorkspace.setText(f"Workspace: {active_project.name}")
        self.window.labelWorkspace.setToolTip(str(active_project))

        # Add the auto-generated toggle action for the log dock to the View menu
        toggle_log_action = self.window.logDockWidget.toggleViewAction()
        toggle_log_action.setText("Show Application Log")
        self.window.menuView.addAction(toggle_log_action)

        # Force the splitter to give the preview pane the lion's share of the window
        self.window.mainSplitter.setSizes([250, 950])

    def connect_signals(self):
        self.actionNewProject.triggered.connect(self.handle_new_project)
        self.actionSettings.triggered.connect(self.handle_settings)
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
            self.config_mgr.set("last_project_path", folder_path)
            
            folder_name = QDir(folder_path).dirName()
            self.window.labelWorkspace.setText(f"Workspace: {folder_name}")
            self.window.labelWorkspace.setToolTip(folder_path)

    def handle_new_project(self):
        dialog = NewProjectDialog(self.window)
        if dialog.exec():
            project_name = dialog.get_project_name()
            new_project = self.project_mgr.create_new_project(project_name)
            self.log(f"Created new project: {new_project}")
            self.tree_manager.update_root(str(new_project))
            self.config_mgr.set("last_project_path", str(new_project))
            
            self.window.labelWorkspace.setText(f"Workspace: {new_project.name}")
            self.window.labelWorkspace.setToolTip(str(new_project))

    def handle_settings(self):
        controller = SettingsDialogController(self.config_mgr, self.window)
        if controller.exec():
            self.log("Settings updated.")
            # Re-apply theme if it changed
            self.apply_theme(self.config_mgr.get("theme"))
            # Update base_projects_dir if it changed
            self.base_projects_dir = self.config_mgr.get("projects_folder")
            self.project_mgr.base_path = Path(self.base_projects_dir)
            # Re-setup icons to match new theme if needed
            self.setup_icons()

    def apply_theme(self, theme):
        if theme == "Dark":
            self.app.setStyle("Fusion")
            self.app.setPalette(self.get_dark_palette())
            self.app.setStyleSheet("QMainWindow { background-color: #2b2b2b; } QToolBar { border: none; }")
        elif theme == "Light":
            self.app.setStyle("Fusion")
            self.app.setPalette(self.app.style().standardPalette())
            self.app.setStyleSheet("")
        else: # System Default
            self.app.setStyle(self.original_style if self.original_style else "")
            self.app.setPalette(self.app.style().standardPalette())
            self.app.setStyleSheet("")

    def get_dark_palette(self):
        from PySide6.QtGui import QColor
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        return dark_palette

    def handle_load_ip(self):
        self.log("Opening Batch Load IP modal...")
        defaults = {
            "load_irms": self.config_mgr.get("default_load_irms"),
            "load_soi": self.config_mgr.get("default_load_soi")
        }
        dialog_controller = LoadIpDialogController(defaults, self.window)

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
