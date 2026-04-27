from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal

class CommandPalette(QDialog):
    """
    Ctrl+K Command Palette for Pro Studio navigation.
    Allows fuzzy-matching of actions, chapters, and UI modes.
    """
    command_executed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setFixedSize(600, 350)
        self.setObjectName("commandPalette")
        
        # Dark Mode Studio Styling matching Phase 6 cleanup
        self.setStyleSheet("""
            QDialog#commandPalette {
                background-color: #1E293B;
                border: 1px solid #475569;
                border-radius: 8px;
            }
            QLineEdit {
                background-color: #0F172A;
                color: #F8FAFC;
                border: none;
                padding: 15px;
                font-size: 16px;
                border-bottom: 1px solid #334155;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QListWidget {
                background-color: #1E293B;
                color: #CBD5E1;
                border: none;
                padding: 5px;
                font-size: 14px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: #3B82F6;
                color: white;
                font-weight: bold;
            }
        """)
        
        # Map human-readable labels to backend system commands
        self.commands_map = {
            "Action: Create New Book": "book",
            "Action: Create New Chapter": "chapter",
            "Action: Save Current Block": "save",
            "Action: Undo/Restore Previous Block Version": "restore_block",
            "Action: Trigger Bulk Import": "import",
            "Action: Global Find & Replace": "replace",
            "Export: Generate Print-Ready PDF (CMYK)": "pdf",
            "Toggle: Focus Mode": "focus",
            "Toggle: Holy Name Highlighter": "highlighter",
            "View: Open Audio Sync & Trim Panel": "audio",
            "View: Return to Library Manager": "library",
            "Search: Focus Library Search": "search"
        }
        
        self.available_commands = list(self.commands_map.keys())
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a command (e.g., Export PDF)...")
        self.search_input.textChanged.connect(self.filter_commands)
        self.search_input.returnPressed.connect(self.execute_selected)
        layout.addWidget(self.search_input)

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.execute_item)
        layout.addWidget(self.list_widget)

        self.populate_list(self.available_commands)

    def populate_list(self, items):
        self.list_widget.clear()
        for item in items:
            QListWidgetItem(item, self.list_widget)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def filter_commands(self, text):
        filtered = [cmd for cmd in self.available_commands if text.lower() in cmd.lower()]
        self.populate_list(filtered)

    def execute_selected(self):
        item = self.list_widget.currentItem()
        if item:
            self.execute_item(item)

    def execute_item(self, item):
        # Emit the backend command ID, not the display text
        action_id = self.commands_map.get(item.text(), item.text())
        self.command_executed.emit(action_id)
        self.close()