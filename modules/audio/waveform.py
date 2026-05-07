"""HTML surface for WebEngine-backed waveform visualization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union


class WaveformHtmlBuilder:
    """Builds an offline-first WaveSurfer.js host page with a canvas fallback."""

    def __init__(self, wavesurfer_asset: Union[str, Path] = "assets/vendor/wavesurfer.min.js"):
        self.wavesurfer_asset = str(wavesurfer_asset).replace("\\", "/")

    def build(self, audio_url: Optional[str] = None) -> str:
        audio_url_json = json.dumps(audio_url or "")
        script_src = json.dumps(self.wavesurfer_asset)
        return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      color-scheme: light;
      --ink: #263238;
      --muted: #607d8b;
      --surface: #f6f8f9;
      --line: #b0bec5;
      --accent: #00796b;
    }}
    html, body {{
      height: 100%;
      margin: 0;
      background: var(--surface);
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
      overflow: hidden;
    }}
    #waveform, #fallback {{
      width: 100%;
      height: 100%;
      min-height: 200px;
    }}
    #fallback {{
      display: none;
    }}
    #message {{
      position: absolute;
      left: 16px;
      bottom: 12px;
      color: var(--muted);
      font-size: 13px;
      background: rgba(246, 248, 249, 0.88);
      padding: 4px 6px;
    }}
  </style>
</head>
<body>
  <div id="waveform"></div>
  <canvas id="fallback"></canvas>
  <div id="message"></div>
  <script>
    const audioUrl = {audio_url_json};
    const waveSurferScript = {script_src};
    const message = document.getElementById("message");

    function drawFallback(label) {{
      const canvas = document.getElementById("fallback");
      const waveform = document.getElementById("waveform");
      waveform.style.display = "none";
      canvas.style.display = "block";

      const ctx = canvas.getContext("2d");
      const width = canvas.clientWidth || 800;
      const height = canvas.clientHeight || 200;
      canvas.width = width * window.devicePixelRatio;
      canvas.height = height * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f6f8f9";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "#cfd8dc";
      ctx.beginPath();
      ctx.moveTo(0, height / 2);
      ctx.lineTo(width, height / 2);
      ctx.stroke();

      const bars = 96;
      const gap = 2;
      const barWidth = Math.max(2, Math.floor(width / bars) - gap);
      ctx.fillStyle = "#00796b";
      for (let index = 0; index < bars; index += 1) {{
        const wave = Math.sin(index * 0.34) * 0.5 + Math.sin(index * 0.11) * 0.35;
        const normalized = Math.max(0.12, Math.min(1, Math.abs(wave)));
        const barHeight = normalized * height * 0.72;
        const x = index * (barWidth + gap);
        const y = (height - barHeight) / 2;
        ctx.fillRect(x, y, barWidth, barHeight);
      }}

      message.textContent = label;
    }}

    function bootWaveSurfer() {{
      if (!window.WaveSurfer || !audioUrl) {{
        drawFallback(audioUrl ? "Static waveform fallback" : "Load audio to activate waveform");
        return;
      }}

      const wavesurfer = WaveSurfer.create({{
        container: "#waveform",
        waveColor: "#80cbc4",
        progressColor: "#00796b",
        cursorColor: "#263238",
        height: 200,
        normalize: true,
        responsive: true
      }});
      wavesurfer.load(audioUrl);
      message.textContent = "WaveSurfer waveform";
    }}

    const script = document.createElement("script");
    script.src = waveSurferScript;
    script.onload = bootWaveSurfer;
    script.onerror = () => drawFallback("WaveSurfer asset missing: using static waveform fallback");
    document.head.appendChild(script);
    window.addEventListener("resize", () => {{
      if (!window.WaveSurfer) {{
        drawFallback(message.textContent || "Static waveform fallback");
      }}
    }});
  </script>
</body>
</html>"""

