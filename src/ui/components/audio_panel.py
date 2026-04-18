import os
import sys
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QTextEdit, QListWidget, QFileDialog, QMessageBox, QGroupBox, QSpinBox)
from PyQt6.QtCore import QThread, pyqtSignal

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.audio.processor import AudioProcessor

class RecipeAudioWorker(QThread):
    finished = pyqtSignal(bool, str)
    
    def __init__(self, recipe_path, source_dir, output_dir, target_lufs):
        super().__init__()
        self.recipe_path = recipe_path
        self.source_dir = source_dir
        self.output_dir = output_dir
        self.target_lufs = target_lufs
        
    def run(self):
        try:
            with open(self.recipe_path, 'r', encoding='utf-8') as f:
                recipe = json.load(f)
                
            processor = AudioProcessor(target_lufs=self.target_lufs)
            processor.build_from_recipe(recipe, self.source_dir, self.output_dir)
            self.finished.emit(True, self.output_dir)
        except Exception as e:
            self.finished.emit(False, str(e))

class AudioPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.audio_file_paths = []
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # -------------------------------------------------------------
        # SECTION 1: SMART RECIPE ROUTING (V4.0 Engine)
        # -------------------------------------------------------------
        recipe_group = QGroupBox("🤖 Smart Recipe Builder (JSON)")
        recipe_group.setStyleSheet("QGroupBox { border: 1px solid #536dfe; border-radius: 8px; margin-top: 10px; font-weight: bold; }")
        recipe_layout = QVBoxLayout()
        
        desc_label = QLabel("Run automated audio generation using a JSON config file (e.g., dalail_audio_recipe.json).")
        desc_label.setStyleSheet("color: #bbbbbb; font-size: 12px;")
        recipe_layout.addWidget(desc_label)
        
        recipe_btns = QHBoxLayout()
        self.run_recipe_btn = QPushButton("🚀 Load Recipe & Build All")
        self.run_recipe_btn.setObjectName("primaryBtn")
        self.run_recipe_btn.clicked.connect(self.handle_run_recipe)
        recipe_btns.addWidget(self.run_recipe_btn)
        recipe_layout.addLayout(recipe_btns)
        
        recipe_group.setLayout(recipe_layout)
        layout.addWidget(recipe_group)

        # -------------------------------------------------------------
        # SECTION 2: LEGACY MANUAL OVERRIDE
        # -------------------------------------------------------------
        legacy_group = QGroupBox("🛠️ Legacy Manual Override")
        legacy_layout = QVBoxLayout()

        self.audio_timeline = QTextEdit()
        self.audio_timeline.setMaximumHeight(80)
        self.audio_timeline.setPlaceholderText("Notes / Timeline... (Tilawat | 2s Gap | Tarjuma)")
        legacy_layout.addWidget(self.audio_timeline)

        audio_controls = QHBoxLayout()
        self.load_audio_btn = QPushButton("📂 Load Audio Files")
        self.load_audio_btn.clicked.connect(self.load_audio_files)
        audio_controls.addWidget(self.load_audio_btn)

        self.stitch_audio_btn = QPushButton("🔗 Stitch Manual")
        self.stitch_audio_btn.clicked.connect(self.stitch_manual)
        audio_controls.addWidget(self.stitch_audio_btn)
        legacy_layout.addLayout(audio_controls)

        self.audio_list_widget = QListWidget()
        legacy_layout.addWidget(self.audio_list_widget)

        legacy_group.setLayout(legacy_layout)
        layout.addWidget(legacy_group)

    def load_audio_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Audio Files", "", "Audio Files (*.mp3 *.wav *.m4a *.ogg)"
        )
        if files:
            self.audio_file_paths = files 
            self.audio_list_widget.clear()
            for f in files:
                self.audio_list_widget.addItem(os.path.basename(f))

    def stitch_manual(self):
        # Existing legacy logic can be called from main window
        pass

    def handle_run_recipe(self):
        # 1. Select JSON Recipe
        recipe_path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio Recipe JSON", "assets", "JSON Files (*.json)"
        )
        if not recipe_path:
            return
            
        # 2. Select Source Directory containing raw tracks (T1.mp3, T2.mp3 etc)
        source_dir = QFileDialog.getExistingDirectory(self, "Select Source Directory containing Raw Audio Files")
        if not source_dir:
            return
            
        # 3. Select Output Directory
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory for Final Playlists")
        if not output_dir:
            return

        self.run_recipe_btn.setEnabled(False)
        self.run_recipe_btn.setText("Processing... Please wait")

        # Start background worker
        self.worker = RecipeAudioWorker(recipe_path, source_dir, output_dir, target_lufs=-16.0)
        self.worker.finished.connect(self.on_recipe_finished)
        self.worker.start()

    def on_recipe_finished(self, success, message):
        self.run_recipe_btn.setEnabled(True)
        self.run_recipe_btn.setText("🚀 Load Recipe & Build All")
        
        if success:
            QMessageBox.information(self, "Success", f"All playlists built successfully in:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Failed to build audio:\n{message}")
