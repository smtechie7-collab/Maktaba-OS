from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

class WebBridge(QObject):
    # Yeh signal tab fire hoga jab HTML mein block par click hoga
    block_clicked = pyqtSignal(int) 

    @pyqtSlot(int)
    def on_block_clicked(self, block_id):
        """JavaScript se call hone wala function"""
        print(f"Bridge Received Click for Block: {block_id}")
        self.block_clicked.emit(block_id)