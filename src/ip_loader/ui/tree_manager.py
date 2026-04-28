from PySide6.QtWidgets import QFileSystemModel, QMenu, QMessageBox
from PySide6.QtCore import QDir, QFileInfo, QFile, Qt, QUrl
from PySide6.QtGui import QDesktopServices

class TreeManager:
    def __init__(self, window, project_mgr, log_callback, preview_panel):
        self.window = window
        self.project_mgr = project_mgr
        self.log = log_callback
        self.preview_panel = preview_panel
        
        self.file_system_model = QFileSystemModel()
        
    def setup_tree(self, root_path):
        self.file_system_model.setRootPath(str(root_path))
        self.window.treeView.setModel(self.file_system_model)
        self.window.treeView.setRootIndex(self.file_system_model.index(str(root_path)))

        # Tell the tree view to emit a signal on right-click
        self.window.treeView.setContextMenuPolicy(Qt.CustomContextMenu)

        # Hide size, type, and date columns
        self.window.treeView.setHeaderHidden(True)
        for i in range(1, 4):
            self.window.treeView.hideColumn(i)
            
    def update_root(self, folder_path):
        self.window.treeView.setRootIndex(self.file_system_model.index(folder_path))

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
                if self.preview_panel.current_preview_path == file_path:
                    self.preview_panel.clear_preview()

            except Exception as e:
                self.log(f"Failed to delete {file_info.fileName()}: {str(e)}")
