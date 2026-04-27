import os
import sys
import json
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                             QLabel, QListWidget, QFileDialog, QMessageBox, 
                             QGroupBox, QSpinBox, QSplitter, QAbstractItemView, QInputDialog,
                             QDoubleSpinBox, QFormLayout, QDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QObject, pyqtSlot
from PyQt6.QtGui import QIcon

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebChannel import QWebChannel
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.audio.processor import AudioProcessor

class AudioWebBridge(QObject):
    time_clicked = pyqtSignal(float)

    @pyqtSlot(float)
    def on_time_clicked(self, current_time):
        self.time_clicked.emit(current_time)

    time_updated = pyqtSignal(float)
    @pyqtSlot(float)
    def on_time_updated(self, current_time):
        self.time_updated.emit(current_time)

class VisualAudioWorker(QThread):
    """Background worker for stitching the visual timeline"""
    finished = pyqtSignal(bool, str)
    def __init__(self, tracks_config, output_path, crossfade_ms, target_lufs):
        super().__init__()
        self.tracks_config = tracks_config
        self.output_path = output_path
        self.crossfade_ms = crossfade_ms
        self.target_lufs = target_lufs
        
    def run(self):
        try:
            processor = AudioProcessor(target_lufs=self.target_lufs)
            processor.process_timeline(self.tracks_config, self.output_path, self.crossfade_ms)
            self.finished.emit(True, self.output_path)
        except Exception as e:
            self.finished.emit(False, str(e))

class AudioPanel(QWidget):
    audio_time_clicked = pyqtSignal(float)
    audio_time_updated = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def update_btn_style(self, btn, obj_name):
        btn.setObjectName(obj_name)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def setup_waveform_view(self, layout):
        """Injects wavesurfer.js via WebEngine for a Pro Studio feel."""
        if not WEB_ENGINE_AVAILABLE:
            fallback = QLabel("Waveform visualizer requires PyQt6-WebEngine.")
            fallback.setStyleSheet("color: #94A3B8; padding: 20px; border: 1px dashed #475569;")
            layout.insertWidget(1, fallback)
            return
            
        self.waveform_view = QWebEngineView()
        self.waveform_view.setFixedHeight(160)
        
        self.audio_bridge = AudioWebBridge()
        self.audio_bridge.time_clicked.connect(self.audio_time_clicked.emit)
        self.audio_bridge.time_updated.connect(self.audio_time_updated.emit)
        self.web_channel = QWebChannel()
        self.web_channel.registerObject("audioBridge", self.audio_bridge)
        self.waveform_view.page().setWebChannel(self.web_channel)

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script src="https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.min.js"></script>
            <style>body { background: #1E293B; color: #94A3B8; margin: 0; padding: 20px; font-family: sans-serif; overflow: hidden; }</style>
        </head>
        <body>
            <div id="waveform"></div>
            <p id="status-text" style="text-align:center; font-size:12px; margin-top: 15px;">Select a track from the library to view waveform & word-sync properties.</p>
            <script>
                const wavesurfer = WaveSurfer.create({ container: '#waveform', waveColor: '#475569', progressColor: '#3B82F6', barWidth: 2, height: 80 });
                new QWebChannel(qt.webChannelTransport, function(channel) { window.audioBridge = channel.objects.audioBridge; });
                wavesurfer.on('interaction', () => { if (window.audioBridge) window.audioBridge.on_time_clicked(wavesurfer.getCurrentTime()); document.getElementById('status-text').innerText = "Timeline Sync: " + wavesurfer.getCurrentTime().toFixed(2) + "s"; });
                wavesurfer.on('timeupdate', (currentTime) => { if (window.audioBridge) window.audioBridge.on_time_updated(currentTime); document.getElementById('status-text').innerText = "Playing: " + currentTime.toFixed(2) + "s"; });
            </script>
        </body>
        </html>
        """
        self.waveform_view.setHtml(html)
        layout.insertWidget(1, self.waveform_view)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel("🎚️ Visual Audio Router (Timeline)")
        header.setObjectName("panelHeader")
        layout.addWidget(header)

        # Inject the interactive Waveform UI
        self.setup_waveform_view(layout)

        # --- SETTINGS BAR ---
        settings_group = QGroupBox("Master Export Settings")
        settings_layout = QHBoxLayout()
        
        self.crossfade_spn = QSpinBox()
        self.crossfade_spn.setRange(0, 5000)
        self.crossfade_spn.setValue(1500)
        self.crossfade_spn.setSuffix(" ms")
        
        self.lufs_spn = QSpinBox()
        self.lufs_spn.setRange(-30, -5)
        self.lufs_spn.setValue(-16)
        self.lufs_spn.setSuffix(" LUFS")

        settings_layout.addWidget(QLabel("<b>Crossfade (Overlap):</b>"))
        settings_layout.addWidget(self.crossfade_spn)
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QLabel("<b>Target Volume:</b>"))
        settings_layout.addWidget(self.lufs_spn)
        settings_layout.addStretch()
        
        self.save_recipe_btn = QPushButton("💾 Save as JSON Recipe")
        self.save_recipe_btn.setObjectName("secondaryBtn")
        self.save_recipe_btn.clicked.connect(self.export_json_recipe)
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
        add_lib_btn.setObjectName("primaryBtn")
        add_lib_btn.clicked.connect(self.load_library_files)
        lib_header.addWidget(add_lib_btn)
        lib_layout.addLayout(lib_header)

        self.library_list = QListWidget()
        self.library_list.setDragEnabled(True) # Can drag items out of here
        self.library_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.library_list.setObjectName("libraryList")
        lib_layout.addWidget(self.library_list)
        splitter.addWidget(lib_widget)

        # 2. TIMELINE PANEL (Right)
        tl_widget = QWidget()
        tl_layout = QVBoxLayout(tl_widget)
        tl_layout.setContentsMargins(0, 0, 0, 0)
        
        tl_header = QHBoxLayout()
        tl_header.addWidget(QLabel("<b>🎞️ Visual Timeline (Drag & Drop here)</b>"))
        clear_tl_btn = QPushButton("🗑️ Clear Timeline")
        clear_tl_btn.setObjectName("dangerBtn")
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
        self.timeline_list.setObjectName("timelineList")
        self.timeline_list.itemDoubleClicked.connect(self.edit_track_trim)
        tl_layout.addWidget(self.timeline_list)
        splitter.addWidget(tl_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        # --- BUILD BUTTON ---
        self.build_btn = QPushButton("🎧 Build Final Audio Track (Export to MP3)")
        self.build_btn.setObjectName("buildBtn")
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
                    item.setData(Qt.ItemDataRole.UserRole, {"path": f, "start": 0.0, "end": None, "name": filename}) 
                    self.library_list.addItem(item)

    def edit_track_trim(self, item):
        """Opens a dialog to trim start/end times of a specific audio track in the timeline."""
        track_data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(track_data, str):
            track_data = {"path": track_data, "start": 0.0, "end": None, "name": os.path.basename(track_data)}
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Trim: {track_data['name']}")
        dialog.setMinimumWidth(300)
        layout = QFormLayout(dialog)
        
        start_spn = QDoubleSpinBox()
        start_spn.setRange(0, 36000)
        start_spn.setDecimals(2)
        start_spn.setValue(track_data.get("start", 0.0))
        start_spn.setSuffix(" s")
        
        end_spn = QDoubleSpinBox()
        end_spn.setRange(0, 36000)
        end_spn.setDecimals(2)
        end_val = track_data.get("end")
        if end_val is None:
            end_spn.setValue(0.0)
            end_spn.setSpecialValueText("End of File")
        else:
            end_spn.setValue(end_val)
        end_spn.setSuffix(" s")
        
        layout.addRow("Start Time:", start_spn)
        layout.addRow("End Time:", end_spn)
        
        btns = QHBoxLayout()
        save_btn = QPushButton("Save Trim")
        save_btn.setObjectName("primaryBtn")
        save_btn.clicked.connect(dialog.accept)
        btns.addWidget(save_btn)
        layout.addRow(btns)
        
        if dialog.exec():
            new_data = {
                "path": track_data["path"],
                "name": track_data["name"],
                "start": start_spn.value(),
                "end": end_spn.value() if end_spn.value() > 0 else None
            }
            item.setData(Qt.ItemDataRole.UserRole, new_data)
            
            end_str = f"{new_data['end']}s" if new_data['end'] else "End"
            if new_data['start'] > 0 or new_data['end']:
                item.setText(f"🎵 {new_data['name']}\n[{new_data['start']}s - {end_str}]")
            else:
                item.setText(f"🎵 {new_data['name']}")
                    
            # Auto-preview the first loaded file in the waveform if available
            if WEB_ENGINE_AVAILABLE and files:
                self.waveform_view.page().runJavaScript(f"wavesurfer.load('file:///{files[0].replace(chr(92), '/')}');")

    def clear_timeline(self):
        self.timeline_list.clear()

    def get_timeline_tracks(self):
        """Extracts the configuration (path, trim data) from the visual timeline."""
        tracks = []
        for i in range(self.timeline_list.count()):
            item = self.timeline_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, str):
                data = {"path": data, "start": 0.0, "end": None, "name": os.path.basename(data)}
            tracks.append(data)
        return tracks

    def export_json_recipe(self):
        """Converts the visual timeline into a recipe.json file for automated routing."""
        tracks = self.get_timeline_tracks()
        if not tracks:
            return QMessageBox.warning(self, "Empty", "Timeline is empty! Drag tracks first.")
        name, ok = QInputDialog.getText(self, "Recipe Name", "Enter a name for this playlist (e.g. Monday_Full):")
        if not ok or not name: return

        # Clean tracks for JSON serialization
        clean_tracks = []
        for t in tracks:
            clean_tracks.append({
                "file": t["name"],
                "start_sec": t["start"],
                "end_sec": t["end"]
            })
        
        recipe_data = {
            name: {
                "tracks": clean_tracks,
                "crossfade": self.crossfade_spn.value(),
                "target_lufs": self.lufs_spn.value()
            }
        }

        save_path, _ = QFileDialog.getSaveFileName(self, "Save Recipe", f"{name}_recipe.json", "JSON Files (*.json)")
        if save_path:
            with open(save_path, 'w') as f:
                json.dump(recipe_data, f, indent=4)
            QMessageBox.information(self, "Saved", f"Recipe saved!\nTo use this, place it in assets/ along with the raw audio files.")

    def build_timeline_audio(self):
        tracks = self.get_timeline_tracks()
        if not tracks:
            return QMessageBox.warning(self, "Empty", "Timeline is empty! Drag tracks from Library to the Timeline.")
            
        out_path, _ = QFileDialog.getSaveFileName(self, "Save Final Mix", "Final_Mix.mp3", "MP3 Files (*.mp3)")
        if not out_path:
            return

        self.build_btn.setEnabled(False)
        self.build_btn.setText("Processing Audio... Please wait (This may take a while)")
        self.update_btn_style(self.build_btn, "buildBtnProcessing")

        self.worker = VisualAudioWorker(
            tracks_config=tracks, 
            output_path=out_path, 
            crossfade_ms=self.crossfade_spn.value(), 
            target_lufs=self.lufs_spn.value()
        )
        self.worker.finished.connect(self.on_build_finished)
        self.worker.start()

    def on_build_finished(self, success, message):
        self.build_btn.setEnabled(True)
        self.build_btn.setText("🎧 Build Final Audio Track (Export to MP3)")
        self.update_btn_style(self.build_btn, "buildBtn")
        
        if success:
            QMessageBox.information(self, "Success", f"Audio Mix successfully exported to:\n{message}")
        else:
            QMessageBox.critical(self, "Error", f"Audio processing failed:\n{message}")
