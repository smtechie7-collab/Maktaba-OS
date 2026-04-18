import os
import sys
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QListWidget, QFileDialog, QMessageBox, 
                             QGroupBox, QSpinBox, QSplitter, QAbstractItemView, QInputDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.audio.processor import AudioProcessor

class VisualAudioWorker(QThread):
    """Background worker for stitching the visual timeline"""
    finished = pyqtSignal(bool, str)
    
    def __init__(self, file_paths, output_path, crossfade_ms, target_lufs):
        super().__init__()
        self.file_paths = file_paths
        self.output_path = output_path
        self.crossfade_ms = crossfade_ms
        self.target_lufs = target_lufs
        
    def run(self):
        try:
            processor = AudioProcessor(target_lufs=self.target_lufs)
            # Using the legacy sequential process for the visual timeline
            processor.process_chapters(self.file_paths, self.output_path, self.crossfade_ms)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class AudioPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel("🎚️ Visual Audio Router (Timeline)")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #0066CC; margin-bottom: 10px;")
        layout.addWidget(header)

        # --- SETTINGS BAR ---
        settings_group = QGroupBox("Master Export Settings")
        settings_group.setStyleSheet("QGroupBox { border: 2px solid #A0A0A0; border-radius: 6px; font-weight: bold; color: #000; } QGroupBox::title { color: #0066CC; left: 10px; padding: 0 5px; }")
        settings_layout = QHBoxLayout()
        
        self.crossfade_spn = QSpinBox()
        self.crossfade_spn.setRange(0, 5000)
        self.crossfade_spn.setValue(1500)
        self.crossfade_spn.setSuffix(" ms")
        self.crossfade_spn.setStyleSheet("background: #FFF; border: 2px solid #A0A0A0; padding: 4px; border-radius: 3px; font-weight: bold;")
        
        self.lufs_spn = QSpinBox()
        self.lufs_spn.setRange(-30, -5)
        self.lufs_spn.setValue(-16)
        self.lufs_spn.setSuffix(" LUFS")
        self.lufs_spn.setStyleSheet("background: #FFF; border: 2px solid #A0A0A0; padding: 4px; border-radius: 3px; font-weight: bold;")

        settings_layout.addWidget(QLabel("<b>Crossfade (Overlap):</b>"))
        settings_layout.addWidget(self.crossfade_spn)
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QLabel("<b>Target Volume:</b>"))
        settings_layout.addWidget(self.lufs_spn)
        settings_layout.addStretch()
        
        self.save_recipe_btn = QPushButton("💾 Save as JSON Recipe")
        self.save_recipe_btn.clicked.connect(self.export_json_recipe)
        self.save_recipe_btn.setStyleSheet("background-color: #E5E7EB; color: #000; font-weight: bold; padding: 6px; border: 1px solid #9CA3AF;")
        settings_layout.addWidget(self.save_recipe_btn)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # --- KINEMASTER STYLE SPLITTER ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 1. LIBRARY PANEL (Left)
        lib_widget = QWidget()
        lib_layout = QVBoxLayout(lib_widget)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        
        lib_header = QHBoxLayout()
        lib_header.addWidget(QLabel("<b>📂 Audio Library (Source)</b>"))
        add_lib_btn = QPushButton("+ Add Files")
        add_lib_btn.setStyleSheet("background-color: #0066CC; color: #FFF; font-weight: bold; border-radius: 3px; padding: 4px;")
        add_lib_btn.clicked.connect(self.load_library_files)
        lib_header.addWidget(add_lib_btn)
        lib_layout.addLayout(lib_header)

        self.library_list = QListWidget()
        self.library_list.setDragEnabled(True) # Can drag items out of here
        self.library_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.library_list.setStyleSheet("""
            QListWidget { background-color: #FFFFFF; border: 2px solid #A0A0A0; border-radius: 4px; }
            QListWidget::item { padding: 8px; border-bottom: 1px solid #E5E7EB; color: #000; font-weight: bold; }
            QListWidget::item:selected { background-color: #E5E7EB; color: #0066CC; border-left: 4px solid #0066CC; }
        """)
        lib_layout.addWidget(self.library_list)
        splitter.addWidget(lib_widget)

        # 2. TIMELINE PANEL (Right)
        tl_widget = QWidget()
        tl_layout = QVBoxLayout(tl_widget)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        
        tl_header = QHBoxLayout()
        tl_header.addWidget(QLabel("<b>🎞️ Visual Timeline (Drag & Drop here)</b>"))
        clear_tl_btn = QPushButton("🗑️ Clear Timeline")
        clear_tl_btn.setStyleSheet("background-color: #DC2626; color: #FFF; font-weight: bold; border-radius: 3px; padding: 4px;")
        clear_tl_btn.clicked.connect(self.clear_timeline)
        tl_header.addWidget(clear_tl_btn)
        tl_layout.addLayout(tl_header)

        self.timeline_list = QListWidget()
        # Make it behave like a horizontal timeline track
        self.timeline_list.setFlow(QListWidget.Flow.LeftToRight)
        self.timeline_list.setWrapping(True) 
        self.timeline_list.setSpacing(10)
        self.timeline_list.setAcceptDrops(True)
        self.timeline_list.setDragEnabled(True)
        self.timeline_list.setViewportMargins(10, 10, 10, 10)
        self.timeline_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.timeline_list.setStyleSheet("""
            QListWidget { 
                background-color: #1E1E1E; /* Dark timeline background */
                border: 2px solid #A0A0A0; border-radius: 4px; 
            }
            QListWidget::item { 
                background-color: #0066CC; color: white; 
                padding: 15px; border-radius: 6px; font-weight: bold; 
                min-width: 100px; text-align: center;
            }
            QListWidget::item:selected { background-color: #0052A3; border: 2px solid #FFF; }
        """)
        tl_layout.addWidget(self.timeline_list)
        splitter.addWidget(tl_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        # --- BUILD BUTTON ---
        self.build_btn = QPushButton("🎧 Build Final Audio Track (Export to MP3)")
        self.build_btn.setStyleSheet("background-color: #0066CC; color: white; font-size: 16px; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.build_btn.clicked.connect(self.build_timeline_audio)
        layout.addWidget(self.build_btn)

    def load_library_files(self):
        """Loads raw audio files into the library list."""
        files, _ = QFileDialog.getOpenFileNames(self, "Select Source Audio Files", "", "Audio Files (*.mp3 *.wav *.m4a)")
        if files:
            for f in files:
                filename = os.path.basename(f)
                # Check if already in library
                exists = False
                for i in range(self.library_list.count()):
                    if self.library_list.item(i).data(Qt.ItemDataRole.UserRole) == f:
                        exists = True
                        break
                
                if not exists:
                    from PyQt6.QtWidgets import QListWidgetItem
                    item = QListWidgetItem(f"🎵 {filename}")
                    item.setData(Qt.ItemDataRole.UserRole, f) # Store full path invisibly
                    self.library_list.addItem(item)

    def clear_timeline(self):
        self.timeline_list.clear()

    def get_timeline_paths(self):
        """Extracts the full file paths from the visual blocks in the timeline in order."""
        paths = []
        for i in range(self.timeline_list.count()):
            item = self.timeline_list.item(i)
            paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def export_json_recipe(self):
        """Converts the visual timeline into a recipe.json file for automated routing."""
        paths = self.get_timeline_paths()
        if not paths:
            return QMessageBox.warning(self, "Empty", "Timeline is empty! Drag tracks first.")
        
        name, ok = QInputDialog.getText(self, "Recipe Name", "Enter a name for this playlist (e.g. Monday_Full):")
        if not ok or not name: return

        # Extract just the filenames for the recipe
        track_names = [os.path.basename(p) for p in paths]
        
        recipe_data = {
            name: {
                "tracks": track_names,
                "crossfade": self.crossfade_spn.value()
            }
        }

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Recipe", f"{name}_recipe.json", "JSON Files (*.json)")
        if save_path:
            with open(save_path, 'w') as f:
                json.dump(recipe_data, f, indent=4)
            QMessageBox.information(self, "Saved", f"Recipe saved!\nTo use this, place it in assets/ along with the raw audio files.")

    def build_timeline_audio(self):
        paths = self.get_timeline_paths()
        if not paths:
            return QMessageBox.warning(self, "Empty", "Timeline is empty! Drag tracks from Library to the Timeline.")

        out_path, _ = QFileDialog.getSaveFileName(self, "Save Final Mix", "Final_Mix.mp3", "MP3 Files (*.mp3)")
        if not out_path:
            return

        self.build_btn.setEnabled(False)
        self.build_btn.setText("Processing Audio... Please wait (This may take a while)")
        self.build_btn.setStyleSheet("background-color: #D97706; color: white; font-size: 16px; font-weight: bold; padding: 12px; border-radius: 6px;")

        self.worker = VisualAudioWorker(
            file_paths=paths, 
            output_path=out_path, 
            crossfade_ms=self.crossfade_spn.value(), 
            target_lufs=self.lufs_spn.value()
        )
        self.worker.finished.connect(self.on_build_finished)
        self.worker.start()

    def on_build_finished(self, success, message):
        self.build_btn.setEnabled(True)
        self.build_btn.setText("🎧 Build Final Audio Track (Export to MP3)")
        self.build_btn.setStyleSheet("background-color: #0066CC; color: white; font-size: 16px; font-weight: bold; padding: 12px; border-radius: 6px;")
        
        if success:
            QMessageBox.information(self, "Success", f"Audio Mix successfully exported to:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Audio processing failed:\n{message}")