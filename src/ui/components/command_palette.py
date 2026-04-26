from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal

class CommandPalette(QDialog):
    command_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.commands = [
            ("New Book", "book"),
            ("New Chapter", "chapter"),
            ("Save Block", "save"),
            ("Export PDF", "pdf"),
            ("Smart Bulk Import", "import"),
            ("Focus Library Search", "search"),
        ]

        self.init_ui()

    def init_ui(self):
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Type a command...")
        self.input.setObjectName("commandPaletteInput")
        self.input.textChanged.connect(self.filter_commands)
        self.input.returnPressed.connect(self.execute_selected)
        
        self.list_widget = QListWidget()
        self.list_widget.setObjectName("commandPaletteList")
        self.list_widget.itemClicked.connect(self.execute_selected)
        
        layout.addWidget(self.input)
        layout.addWidget(self.list_widget)
        
        self.populate_list()
        
        self.setStyleSheet("""
            QDialog {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QLineEdit#commandPaletteInput {
                padding: 16px;
                font-size: 18px;
                border: none;
                background: transparent;
                color: #F8FAFC;
                border-bottom: 1px solid #334155;
            }
            QListWidget#commandPaletteList {
                border: none;
                background: transparent;
                padding: 8px;
                outline: none;
                font-size: 16px;
            }
            QListWidget#commandPaletteList::item {
                padding: 12px;
                color: #CBD5E1;
                border-radius: 6px;
                margin-bottom: 4px;
            }
            QListWidget#commandPaletteList::item:selected {
                background-color: #334155;
                color: #F8FAFC;
            }
            QListWidget#commandPaletteList::item:hover {
                background-color: #334155;
            }
        """)

    def populate_list(self, filter_text=""):
        self.list_widget.clear()
        filter_text = filter_text.lower()
        for display, cmd in self.commands:
            if filter_text in display.lower() or filter_text in cmd.lower():
                item = QListWidgetItem(f"⚡ {display}")
                item.setData(Qt.ItemDataRole.UserRole, cmd)
                self.list_widget.addItem(item)
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def filter_commands(self, text):
        self.populate_list(text)

    def execute_selected(self):
        item = self.list_widget.currentItem()
        if item:
            cmd = item.data(Qt.ItemDataRole.UserRole)
            self.command_selected.emit(cmd)
            self.accept()
        else:
            self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Up:
            row = self.list_widget.currentRow()
            if row > 0:
                self.list_widget.setCurrentRow(row - 1)
        elif event.key() == Qt.Key.Key_Down:
            row = self.list_widget.currentRow()
            if row < self.list_widget.count() - 1:
                self.list_widget.setCurrentRow(row + 1)
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)
