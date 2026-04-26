from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal

class WebBridge(QObject):
    # Yeh signal tab fire hoga jab HTML mein block par click hoga
    block_clicked = pyqtSignal(int) 
    
    # Naya signal: Jab user directly preview me text type karke edit karega
    block_edited = pyqtSignal(int, str, str)

    @pyqtSlot(int)
    def on_block_clicked(self, block_id):
        """JavaScript se call hone wala function"""
        self.block_clicked.emit(block_id)

    @pyqtSlot(int, str, str)
    def on_block_edited(self, block_id, lang, new_text):
        """JS se Live Edit data receive karega"""
        self.block_edited.emit(block_id, lang, new_text)