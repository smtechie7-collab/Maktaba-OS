"""
Sync Mode widget for Maktaba-OS audio synchronization interface.
Implements spacebar-driven timestamp mapping and waveform visualization.
"""

from typing import Optional, Dict, Any
from pathlib import Path
import json

from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QKeySequence, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QSlider, QTextEdit, QSplitter, QFrame, QProgressBar
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

        self.current_position = 0.0  # seconds
        self.timestamps: Dict[str, float] = {}  # word_id -> timestamp

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

        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMinimumHeight(200)
        bottom_layout.addWidget(self.text_display)

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
            url = QUrl.fromLocalFile(file_path)
            self.audio_player.setSource(url)
            self.status_label.setText(f"Loaded: {Path(file_path).name}")
            self.play_pause_btn.setText("Play")
            self.position_slider.setValue(0)
            self.time_label.setText("00:00 / 00:00")

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
        # For now, just show current position
        self.status_label.setText(f"Marked at {self.current_position:.2f}s")

    def clear_timestamps(self):
        """Clear all timestamps."""
        self.timestamps.clear()
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
            # Load text content
            text_content = self._extract_text_content(chapter)
            self.text_display.setPlainText(text_content)
        else:
            self.book_label.setText("Failed to load book")

    def _extract_text_content(self, chapter) -> str:
        """Extract text content from chapter for display."""
        lines = []
        for block in chapter.children:
            if hasattr(block, 'ar') and block.ar:
                lines.append(f"AR: {block.ar}")
            if hasattr(block, 'ur') and block.ur:
                lines.append(f"UR: {block.ur}")
            if hasattr(block, 'en') and block.en:
                lines.append(f"EN: {block.en}")
        return "\n".join(lines)

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