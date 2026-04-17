import os
import requests
import sys

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.logger import setup_logger

logger = setup_logger("FontSetup")

FONTS = {
    "Amiri-Regular.ttf": "https://github.com/googlefonts/amiri/raw/main/fonts/ttf/Amiri-Regular.ttf",
    "Amiri-Bold.ttf": "https://github.com/googlefonts/amiri/raw/main/fonts/ttf/Amiri-Bold.ttf",
}

def download_fonts():
    """Download required fonts into assets/fonts/ if they don't exist."""
    font_dir = "assets/fonts"
    os.makedirs(font_dir, exist_ok=True)

    for font_name, url in FONTS.items():
        font_path = os.path.join(font_dir, font_name)
        if not os.path.exists(font_path):
            logger.info(f"Downloading {font_name}...")
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                with open(font_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"Successfully downloaded {font_name}")
            except Exception as e:
                logger.error(f"Failed to download {font_name}: {e}")
        else:
            logger.info(f"{font_name} already exists.")

if __name__ == "__main__":
    download_fonts()
