import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QFileSystemModel, QFileDialog, QDialog,
    QMenu, QMessageBox  # <-- Add these two
)
from PySide6.QtCore import (
    QThreadPool, QFile, QDir, QStandardPaths, QFileInfo, QUrl, Qt # <-- Add Qt
)
from PySide6.QtGui import QDesktopServices, QPalette
from PySide6.QtUiTools import QUiLoader

import qtawesome as qta  # Import the new library

# Custom modules
from project_manager import ProjectManager
from downloader_interfaces import DownloadWorker
from dialog_controllers import (
    LoadIpDialogController,
    LoadIrmsDialogController,
    LoadSoiDialogController,
    CompareSoiDialogController
)
import csv
import openpyxl
from PySide6.QtWidgets import QTableWidgetItem


class ApplicationController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.thread_pool = QThreadPool()
        self.active_irm_dialog = None
        self.current_preview_path = None

        # 1. Load the UI XML
        self.load_ui()

        # 2. Setup standard icons
        self.setup_icons()

        # 3. Find Documents folder and initialize the Project Manager
        docs_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        self.base_projects_dir = QDir(docs_path).filePath("IP_Projects")
        self.project_mgr = ProjectManager(self.base_projects_dir)

        # 4. Setup models and signals
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

    def setup_icons(self):
        # Determine if Windows is in dark mode based on the default text color
        palette = self.app.palette()
        is_dark_mode = palette.color(QPalette.WindowText).lightness() > palette.color(QPalette.Window).lightness()

        # Pick a clean icon color based on the theme
        icon_color = '#FFFFFF' if is_dark_mode else '#333333'

        # fa5s = FontAwesome 5 Solid. You can browse their cheat sheet online for names.
        self.window.actionOpenFolder.setIcon(qta.icon('ph.folder-open', color=icon_color))
        self.window.actionLoadIP.setIcon(qta.icon('ph.folder-plus', color=icon_color))
        self.window.actionLoadIRMs.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionLoadSOI.setIcon(qta.icon('ph.cloud-arrow-down', color=icon_color))
        self.window.actionCompareSOI.setIcon(qta.icon('ph.git-diff', color=icon_color))

    def setup_models(self):
        # Create a default active project so the workspace isn't empty on launch
        default_project = self.project_mgr.create_new_project()

        self.file_system_model = QFileSystemModel()
        self.file_system_model.setRootPath(str(default_project))

        self.window.treeView.setModel(self.file_system_model)
        self.window.treeView.setRootIndex(self.file_system_model.index(str(default_project)))

        # Tell the tree view to emit a signal on right-click
        self.window.treeView.setContextMenuPolicy(Qt.CustomContextMenu)

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

        # Force the splitter to give the preview pane the lion's share of the window
        self.window.mainSplitter.setSizes([250, 950])

    def connect_signals(self):
        self.window.actionOpenFolder.triggered.connect(self.handle_open_folder)
        self.window.actionLoadIP.triggered.connect(self.handle_load_ip)
        self.window.actionLoadIRMs.triggered.connect(self.handle_load_irms)
        self.window.actionLoadSOI.triggered.connect(self.handle_load_soi)
        self.window.actionCompareSOI.triggered.connect(self.handle_compare_soi)
        self.window.treeView.clicked.connect(self.handle_file_selection)
        self.window.treeView.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.window.btnOpenPdf.clicked.connect(self.open_external_pdf)

    def show_tree_context_menu(self, pos):
        # Find out what item is under the mouse cursor
        index = self.window.treeView.indexAt(pos)

        # If the user right-clicked empty space, do nothing
        if not index.isValid():
            return

        file_path = self.file_system_model.filePath(index)
        file_info = QFileInfo(file_path)

        # Create the menu
        menu = QMenu(self.window)
        action_open_sys = menu.addAction("Open in File Explorer")
        menu.addSeparator()  # Visual divider
        action_delete = menu.addAction("Delete")

        # Map the widget coordinates to global screen coordinates so the menu spawns correctly
        global_pos = self.window.treeView.viewport().mapToGlobal(pos)

        # Execute the menu and halt until the user clicks something or clicks away
        selected_action = menu.exec(global_pos)

        if selected_action == action_open_sys:
            # If they clicked a file, open its parent folder. If it's a directory, open it directly.
            dir_to_open = file_info.absoluteFilePath() if file_info.isDir() else file_info.absolutePath()
            QDesktopServices.openUrl(QUrl.fromLocalFile(dir_to_open))

        elif selected_action == action_delete:
            self.delete_item_safely(file_path, file_info)

    def delete_item_safely(self, file_path, file_info):
        # Never delete files without a confirmation trap
        reply = QMessageBox.question(
            self.window,
            "Confirm Delete",
            f"Are you sure you want to permanently delete:\n{file_info.fileName()}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No  # Default to 'No' so hitting Enter doesn't accidentally wipe data
        )

        if reply == QMessageBox.Yes:
            try:
                if file_info.isDir():
                    # removeRecursively wipes the folder and everything inside it
                    QDir(file_path).removeRecursively()
                else:
                    QFile.remove(file_path)

                self.log(f"Deleted: {file_info.fileName()}")

                # If they deleted the file they were actively previewing, clear the preview pane
                if self.current_preview_path == file_path:
                    self.window.previewStack.setCurrentIndex(0)
                    self.window.htmlPreviewer.setHtml("<h2>File Deleted</h2>")
                    self.current_preview_path = None

            except Exception as e:
                self.log(f"Failed to delete {file_info.fileName()}: {str(e)}")

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

    # Update this method in main.py
    def spawn_download_task(self, task_type, ip_num, ln_num, **kwargs):
        if self.project_mgr.active_project_path:
            ip_dir = self.project_mgr.active_project_path / f"{ip_num}-{ln_num}"
            kwargs['save_path'] = str(ip_dir)

        # Inject the active SSO session into kwargs so the worker can use VelocityClient
        # This assumes you initialized self.sso_session in ApplicationController.__init__
        kwargs['sso_session'] = getattr(self, 'sso_session', None)

        worker = DownloadWorker(task_type, ip_num, ln_num, **kwargs)
        worker.signals.log_msg.connect(self.log)
        worker.signals.finished.connect(self.on_download_finished)
        worker.signals.error.connect(self.on_download_error)
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

    def handle_file_selection(self, index):
        file_path = self.file_system_model.filePath(index)
        file_info = QFileInfo(file_path)

        if file_info.isDir():
            return

        self.current_preview_path = file_path
        extension = file_info.suffix().lower()

        if extension == "html":
            self.window.previewStack.setCurrentIndex(0)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.window.htmlPreviewer.setHtml(f.read())
            except Exception as e:
                self.window.htmlPreviewer.setPlainText(f"Error reading HTML:\n{str(e)}")

        elif extension == "pdf":
            self.window.previewStack.setCurrentIndex(1)
            self.window.labelPdfNotice.setText(f"<b>3D PDF Selected:</b><br>{file_info.fileName()}")

        elif extension == "csv":
            self.window.previewStack.setCurrentIndex(2)
            self.window.labelDataNotice.setText(f"Previewing CSV: {file_info.fileName()} (First 500 rows)")
            self.preview_csv(file_path)

        elif extension in ["xlsx", "xls"]:
            self.window.previewStack.setCurrentIndex(2)
            self.window.labelDataNotice.setText(f"Previewing Excel: {file_info.fileName()} (First 500 rows)")
            self.preview_excel(file_path)

        else:
            self.window.previewStack.setCurrentIndex(0)
            self.window.htmlPreviewer.setHtml(f"<h2>File Selected</h2><p>{file_info.fileName()}</p>")

    def preview_csv(self, file_path):
        self.window.dataPreviewTable.clear()
        self.window.dataPreviewTable.setRowCount(0)
        self.window.dataPreviewTable.setColumnCount(0)

        try:
            with open(file_path, mode='r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                data = list(reader)

                if not data:
                    return

                # Cap at 500 to prevent GUI lockups
                preview_data = data[:500]

                self.window.dataPreviewTable.setColumnCount(len(preview_data[0]))
                self.window.dataPreviewTable.setRowCount(len(preview_data))

                for row_idx, row_data in enumerate(preview_data):
                    for col_idx, cell_data in enumerate(row_data):
                        self.window.dataPreviewTable.setItem(row_idx, col_idx, QTableWidgetItem(str(cell_data)))
        except Exception as e:
            self.log(f"Failed to preview CSV: {str(e)}")

    def preview_excel(self, file_path):
        self.window.dataPreviewTable.clear()
        self.window.dataPreviewTable.setRowCount(0)
        self.window.dataPreviewTable.setColumnCount(0)

        try:
            # read_only mode is critical here for performance on large files
            wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
            sheet = wb.active

            data = []
            for row in sheet.iter_rows(values_only=True, max_row=500):
                data.append(row)

            if not data:
                return

            # Find the widest row in case the data is jagged
            max_cols = max(len(r) for r in data if r)
            self.window.dataPreviewTable.setColumnCount(max_cols)
            self.window.dataPreviewTable.setRowCount(len(data))

            for row_idx, row_data in enumerate(data):
                if not row_data:
                    continue
                for col_idx, cell_data in enumerate(row_data):
                    val = str(cell_data) if cell_data is not None else ""
                    self.window.dataPreviewTable.setItem(row_idx, col_idx, QTableWidgetItem(val))

        except Exception as e:
            self.log(f"Failed to preview Excel file: {str(e)}")

    def open_external_pdf(self):
        if self.current_preview_path:
            # This asks the OS to open the file with whatever default app the user has registered
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_preview_path))
            self.log(f"Opened externally: {QFileInfo(self.current_preview_path).fileName()}")

    def run(self):
        self.window.show()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    controller = ApplicationController()
    controller.run()
