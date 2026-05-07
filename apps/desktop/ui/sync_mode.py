"""
Sync Mode widget for Maktaba-OS audio synchronization interface.
Implements spacebar-driven timestamp mapping and waveform visualization.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import json

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeySequence, QAction, QBrush, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QSlider, QSplitter, QFrame, QProgressBar, QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False
    QWebEngineView = None  # type: ignore

from infrastructure.config.app_config import load_config
from infrastructure.database.manager import DatabaseManager

from core.engine.document_engine import DocumentEngine
from core.commands.command_bus import CommandBus
from core.commands.commands import ReplaceDocumentCommand

from modules.audio.processor import AudioProcessor


class SyncModeWidget(QWidget):
    """Main widget for Sync Mode audio synchronization."""

    def __init__(self, command_bus: CommandBus, parent=None):
        super().__init__(parent)
        self.command_bus = command_bus
        self.config = load_config()
        self.db_manager = DatabaseManager(self.config.db_path)
        self.document_engine = DocumentEngine(self.db_manager)
        self.audio_processor = AudioProcessor()

        self.current_book_id: Optional[int] = None
        self.audio_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.audio_player.setAudioOutput(self.audio_output)

        self.current_audio_path: Optional[str] = None
        self.current_position = 0.0  # seconds
        self.timestamps: Dict[str, float] = {}  # word_id -> timestamp
        self.word_nodes: list = []  # List of ordered word IDs
        self.current_word_index = 0

        self.init_ui()
        self.setup_audio_player()
        self.setup_shortcuts()

    def init_ui(self):
        """Initialize the sync mode UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_layout = QHBoxLayout()
        header_label = QLabel("Sync Mode - Audio Synchronization")
        header_label.setStyleSheet("font-weight: bold; font-size: 16px;")
        header_layout.addWidget(header_label)

        self.book_label = QLabel("No book loaded")
        header_layout.addWidget(self.book_label)

        header_layout.addStretch()

        self.load_audio_btn = QPushButton("Load Audio")
        self.load_audio_btn.clicked.connect(self.load_audio_file)
        header_layout.addWidget(self.load_audio_btn)

        self.export_audio_btn = QPushButton("Export Normalized Audio")
        self.export_audio_btn.clicked.connect(self.export_normalized_audio)
        header_layout.addWidget(self.export_audio_btn)

        layout.addLayout(header_layout)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Top: Waveform and controls
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        # Waveform visualization (placeholder for now)
        if WEBENGINE_AVAILABLE and QWebEngineView:
            self.waveform_view = QWebEngineView()
            self.waveform_view.setMinimumHeight(200)
            self.waveform_view.setHtml(self._get_waveform_html())
        else:
            self.waveform_view = QLabel("Waveform visualization requires PyQt6-WebEngine\nPlease install: pip install PyQt6-WebEngine")
            self.waveform_view.setMinimumHeight(200)
            self.waveform_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.waveform_view.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        top_layout.addWidget(self.waveform_view)

        # Audio controls
        controls_layout = QHBoxLayout()

        self.play_pause_btn = QPushButton("Play")
        self.play_pause_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_pause_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_playback)
        controls_layout.addWidget(self.stop_btn)

        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.sliderMoved.connect(self.seek_position)
        controls_layout.addWidget(self.position_slider)

        # Time display
        self.time_label = QLabel("00:00 / 00:00")
        controls_layout.addWidget(self.time_label)

        # Speed control
        speed_label = QLabel("Speed:")
        controls_layout.addWidget(speed_label)

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)  # 0.5x to 2x
        self.speed_slider.setValue(100)
        self.speed_slider.valueChanged.connect(self.change_speed)
        controls_layout.addWidget(self.speed_slider)

        self.speed_label = QLabel("1.0x")
        controls_layout.addWidget(self.speed_label)

        top_layout.addLayout(controls_layout)

        splitter.addWidget(top_widget)

        # Bottom: Text with timestamps
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        text_label = QLabel("Text with Timestamps (Press Spacebar to mark current word)")
        text_label.setStyleSheet("font-weight: bold;")
        bottom_layout.addWidget(text_label)

        self.word_list = QListWidget()
        self.word_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.word_list.setMinimumHeight(200)
        self.word_list.setStyleSheet("QListWidget::item { padding: 5px; font-size: 14px; }")
        bottom_layout.addWidget(self.word_list)

        # Timestamp controls
        timestamp_layout = QHBoxLayout()

        self.mark_word_btn = QPushButton("Mark Word (Space)")
        self.mark_word_btn.clicked.connect(self.mark_current_word)
        timestamp_layout.addWidget(self.mark_word_btn)

        self.clear_timestamps_btn = QPushButton("Clear Timestamps")
        self.clear_timestamps_btn.clicked.connect(self.clear_timestamps)
        timestamp_layout.addWidget(self.clear_timestamps_btn)

        self.export_timestamps_btn = QPushButton("Export Timestamps")
        self.export_timestamps_btn.clicked.connect(self.export_timestamps)
        timestamp_layout.addWidget(self.export_timestamps_btn)

        bottom_layout.addLayout(timestamp_layout)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([400, 300])

        layout.addWidget(splitter)

        # Status bar
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

    def setup_audio_player(self):
        """Setup audio player connections."""
        self.audio_player.positionChanged.connect(self.update_position)
        self.audio_player.durationChanged.connect(self.update_duration)
        self.audio_player.playbackStateChanged.connect(self.update_playback_state)

    def setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Spacebar for marking timestamps
        space_action = QAction(self)
        space_action.setShortcut(QKeySequence(Qt.Key.Key_Space))
        space_action.triggered.connect(self.mark_current_word)
        self.addAction(space_action)

    def load_audio_file(self):
        """Load an audio file for synchronization."""
        # For now, just show a message
        self.status_label.setText("Audio loading not implemented yet - use placeholder")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Audio File",
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.m4a);;All Files (*)"
        )
        if file_path:
            self.current_audio_path = file_path
            url = QUrl.fromLocalFile(file_path)
            self.audio_player.setSource(url)
            self.status_label.setText(f"Loaded: {Path(file_path).name}")
            self.play_pause_btn.setText("Play")
            self.position_slider.setValue(0)
            self.time_label.setText("00:00 / 00:00")

    def export_normalized_audio(self):
        """Export the currently loaded audio, applying EBU R128 normalization."""
        if not self.current_audio_path:
            self.status_label.setText("No audio loaded to export.")
            return

        if not self.audio_processor.has_ffmpeg():
            self.status_label.setText("Export failed: FFmpeg is required but not found on the system.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Normalized Audio",
            "",
            "Audio Files (*.wav *.mp3 *.ogg *.m4a);;All Files (*)"
        )
        if file_path:
            try:
                self.status_label.setText("Normalizing audio... please wait.")
                QApplication.processEvents()  # Force UI update before blocking task
                
                out_path = self.audio_processor.normalize_audio(self.current_audio_path, file_path)
                self.status_label.setText(f"Successfully exported normalized audio to {out_path.name}")
            except Exception as e:
                self.status_label.setText(f"Failed to export audio: {str(e)}")

    def toggle_playback(self):
        """Toggle play/pause."""
        if self.audio_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.audio_player.pause()
        else:
            self.audio_player.play()

    def stop_playback(self):
        """Stop playback."""
        self.audio_player.stop()

    def seek_position(self, position):
        """Seek to position in audio."""
        duration = self.audio_player.duration()
        if duration > 0:
            seek_pos = int((position / 1000) * duration)
            self.audio_player.setPosition(seek_pos)

    def change_speed(self, value):
        """Change playback speed."""
        speed = value / 100.0
        self.audio_output.setVolume(speed)  # Note: This is not speed, but we'll implement proper speed later
        self.speed_label.setText(f"{speed:.1f}x")

    def update_position(self, position):
        """Update position display."""
        duration = self.audio_player.duration()
        if duration > 0:
            self.position_slider.blockSignals(True)
            self.position_slider.setValue(int((position / duration) * 1000))
            self.position_slider.blockSignals(False)

            pos_str = self._format_time(position)
            dur_str = self._format_time(duration)
            self.time_label.setText(f"{pos_str} / {dur_str}")

            self.current_position = position / 1000.0  # Convert to seconds

    def update_duration(self, duration):
        """Update duration when media loads."""
        dur_str = self._format_time(duration)
        self.time_label.setText(f"00:00 / {dur_str}")

    def update_playback_state(self, state):
        """Update play/pause button text."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setText("Pause")
        else:
            self.play_pause_btn.setText("Play")

    def mark_current_word(self):
        """Mark the current word with timestamp."""
        if not self.word_nodes:
            self.status_label.setText("No text loaded.")
            return
            
        if self.current_word_index >= len(self.word_nodes):
            self.status_label.setText("All words synchronized!")
            return

        node_id = self.word_nodes[self.current_word_index]
        timestamp = self.current_position
        self.timestamps[node_id] = timestamp
        
        # Update UI item visually
        item = self.word_list.item(self.current_word_index)
        time_str = self._format_time(int(timestamp * 1000))
        base_text = item.text().split(" [")[0]
        item.setText(f"{base_text} [{time_str}]")
        item.setForeground(QBrush(QColor("#008000")))  # Highlight synced words in green
        
        # Move to next word
        self.current_word_index += 1
        if self.current_word_index < len(self.word_nodes):
            self.word_list.setCurrentRow(self.current_word_index)
            self.word_list.scrollToItem(self.word_list.item(self.current_word_index))
            
        self.status_label.setText(f"Marked word {self.current_word_index} at {timestamp:.2f}s")

    def clear_timestamps(self):
        """Clear all timestamps."""
        self.timestamps.clear()
        self.current_word_index = 0
        
        for i in range(self.word_list.count()):
            item = self.word_list.item(i)
            base_text = item.text().split(" [")[0]
            item.setText(base_text)
            item.setForeground(QBrush())  # Reset color
            
        if self.word_list.count() > 0:
            self.word_list.setCurrentRow(0)
            
        self.status_label.setText("Timestamps cleared")

    def export_timestamps(self):
        """Export timestamps to file."""
        self.status_label.setText("Timestamp export not implemented yet")
        if not self.timestamps:
            self.status_label.setText("No timestamps to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Timestamps", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.timestamps, f, indent=2, ensure_ascii=False)
                self.status_label.setText(f"Exported to {Path(file_path).name}")
            except Exception as e:
                self.status_label.setText(f"Export failed: {str(e)}")

    def load_book(self, book_id: int):
        """Load a book for synchronization."""
        self.current_book_id = book_id
        document = self.document_engine.load_document(book_id)
        if document and document.children:
            chapter = document.children[0]
            self.book_label.setText(f"Book: {chapter.title}")
            self._populate_word_list(chapter)
        else:
            self.book_label.setText("Failed to load book")

    def _populate_word_list(self, chapter):
        """Extract strictly typed word bundles and prepare the list view."""
        self.word_list.clear()
        self.word_nodes.clear()
        self.timestamps.clear()
        self.current_word_index = 0
        
        # Adhere to schema: interlinear_block -> content -> word_bundles
        for block_idx, block in enumerate(chapter.children):
            bundles = getattr(block, 'content', getattr(block, 'children', []))
            
            for bundle_idx, bundle in enumerate(bundles):
                # Safely extract attributes regardless of whether model is dict or object
                node_id = getattr(bundle, 'id', f"{block_idx}_{bundle_idx}")
                
                # Accommodate various schema versions (ar/ur/en vs l1/l2/l3)
                ar = getattr(bundle, 'ar', getattr(bundle, 'l1', ''))
                ur = getattr(bundle, 'ur', getattr(bundle, 'l2', ''))
                en = getattr(bundle, 'en', getattr(bundle, 'l3', ''))
                
                display_text = " | ".join(filter(None, [ar, ur, en]))
                
                if display_text:
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.ItemDataRole.UserRole, node_id)
                    self.word_list.addItem(item)
                    self.word_nodes.append(node_id)
                    
        if self.word_list.count() > 0:
            self.word_list.setCurrentRow(0)

    def _format_time(self, ms: int) -> str:
        """Format milliseconds to MM:SS."""
        total_seconds = ms // 1000
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _get_waveform_html(self) -> str:
        """Get placeholder HTML for waveform visualization."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { margin: 0; background: #f0f0f0; }
                .waveform { height: 200px; background: #e0e0e0; display: flex; align-items: center; justify-content: center; }
                .placeholder { color: #666; font-family: Arial; }
            </style>
        </head>
        <body>
            <div class="waveform">
                <div class="placeholder">Waveform Visualization<br>(WaveSurfer.js integration pending)</div>
            </div>
        </body>
        </html>
        """