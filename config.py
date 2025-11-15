"""
MOHID HDF5 Viewer - Configuration and Constants
"""
from typing import List, Tuple
import logging

# ===================== LOGGING CONFIGURATION =====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ===================== APPLICATION METADATA =====================
APP_TITLE = "MOHID HDF5 Viewer"
APP_VERSION = "2.0"
APP_AUTHORS = [
    "Giulliano de Lima Lopes de Oliveira Simeão Bigão",
    "Nikolas Gomes Silveira de Souza",
    "Rogerio Atem de Carvalho",
    "Jader Lugon Jr."
]
APP_DESCRIPTION = """
A comprehensive, interactive utility to inspect and export data from MOHID HDF5 files
into various formats, including animations (MP4, GIF, AVI), frame-by-frame images (JPG),
geospatial data (GeoTIFF), and raw text (CSV).
Tested with Land HDF files and Hydrodynamic in Water HDF Files.
"""


# ===================== UI CONSTANTS =====================
class UIConfig:
    """UI Layout and sizing constants"""
    # Window positions
    MAIN_WINDOW_LOCATION = (120, 60)
    VIEWER_WINDOW_LOCATION = (780, 40)
    
    # Figure sizes
    FIGURE_SIZE = (12, 8)
    FIGURE_DPI_DEFAULT = 120
    FIGURE_DPI_MIN = 90
    FIGURE_DPI_MAX = 200
    
    # Axes positions [left, bottom, width, height]
    MAIN_AXES = [0.05, 0.05, 0.8, 0.85]
    MAIN_AXES_NO_TILES = [0.06, 0.06, 0.78, 0.88]
    COLORBAR_AXES = [0.87, 0.15, 0.03, 0.7]
    COLORBAR_AXES_ALT = [0.86, 0.18, 0.03, 0.64]
    
    # Viewer canvas for colorbar preview
    COLORBAR_PREVIEW_SIZE = (600, 20)
    
    # Font settings
    DEFAULT_FONT = 'Helvetica 10'
    TITLE_FONT = ("Helvetica", 14, "bold")
    CONSOLE_FONT = ("Consolas", 10)


# ===================== BASEMAP OPTIONS =====================
BASEMAP_OPTIONS: List[str] = [
    "Google Satellite (imagery)",
    "Google Terrain",
    "OpenStreetMap",
    "None",
]

TILE_ZOOM_MIN = 1
TILE_ZOOM_MAX = 21
TILE_ZOOM_DEFAULT = 12


# ===================== COLORMAP OPTIONS =====================
COLOR_SCALE_OPTIONS: List[str] = [
    "rainbow",
    "viridis",
    "plasma",
    "inferno",
    "magma",
    "cividis",
    "Grays",
    "Purples",
    "Blues",
    "Greens",
    "Oranges",
    "Reds",
    "YlOrBr",
    "YlOrRd",
    "OrRd",
    "PuRd",
    "RdPu",
    "BuPu",
    "GnBu",
    "PuBu",
    "YlGnBu",
    "PuBuGn",
    "BuGn",
    "YlGn",
    "binary",
    "gist_yarg",
    "gist_gray",
    "gray",
    "bone",
    "pink",
    "spring",
    "summer",
    "autumn",
    "winter",
    "cool",
    "Wistia",
    "hot",
    "afmhot",
    "gist_heat",
    "copper"
]


# ===================== EXPORT FORMATS =====================
EXPORT_FORMATS: List[str] = [
    "Image sequence (jpg)",
    "Animation (mp4)",
    "Animation (gif)",
    "Animation (avi)",
    "Geospatial Data (geotiff)",
    "Raw Data (csv) [VERY SLOW, LARGE FILES]"
]


# ===================== DATA PROCESSING CONSTANTS =====================
class DataConfig:
    """Constants for data processing"""
    # NoData handling
    DEFAULT_NODATA_VALUES = [-99.0, -9.9e15]
    AUTO_LAND_THRESHOLD = -1e12
    TIFF_NODATA_VALUE = -9999.0
    
    # Tolerances
    NODATA_TOLERANCE_FACTOR = 1e-8
    
    # Grid alignment
    MIN_INTERFACE_SIZE = 2
    
    # Statistics
    DEFAULT_STATS_FRAMES = 6
    
    # Animation
    DEFAULT_FPS = 6
    DEFAULT_CONTOUR_LEVELS = 11
    
    # Progress reporting
    PROGRESS_UPDATE_INTERVAL = 1


# ===================== FILE PATTERNS =====================
class FilePatterns:
    """Regular expressions for file parsing"""
    TIMESTAMP_PATTERN = r'_(\d{8}_\d{4})\.jpg$'
    SAFE_FILENAME_PATTERN = r'[^A-Za-z0-9_.-]+'


# ===================== MESSAGES (i18n ready) =====================
MESSAGES = {
    'pt_BR': {
        'file_not_found': 'Arquivo não encontrado em',
        'no_variables': 'Nenhuma variável encontrada em Results/',
        'choose_variable': 'Por favor, escolha uma variável!',
        'choose_format': 'Por favor, escolha um formato de exportação!',
        'export_complete': 'Exportação concluída',
        'error_export': 'Erro durante a exportação',
        'no_jpg_export': 'Nenhuma exportação JPG encontrada. Exporte como JPG primeiro.',
        'folder_not_found': 'Pasta não encontrada ou não acessível.',
        'no_k_list': 'Não há lista k (sem arquivo ou variável 2-D)!',
        'no_k_refresh': 'Sem lista k para atualizar!',
        'viewer_open': 'Abra o Viewer para inspecionar.',
        'loading_error': 'Não foi possível carregar os dados da variável selecionada.',
    },
    'en_US': {
        'file_not_found': 'File not found at',
        'no_variables': 'No variables found in Results/',
        'choose_variable': 'Please choose a variable!',
        'choose_format': 'Please choose an export format!',
        'export_complete': 'Export completed',
        'error_export': 'Error during export',
        'no_jpg_export': 'No JPG export found. Export as JPG first.',
        'folder_not_found': 'Folder not found or not accessible.',
        'no_k_list': 'No k list (no file or 2-D variable)!',
        'no_k_refresh': 'No k list to refresh!',
        'viewer_open': 'Open Viewer to inspect.',
        'loading_error': 'Could not load data for selected variable.',
    }
}

# Current language
CURRENT_LANGUAGE = 'pt_BR'


def get_message(key: str, lang: str = None) -> str:
    """Get localized message"""
    if lang is None:
        lang = CURRENT_LANGUAGE
    return MESSAGES.get(lang, MESSAGES['en_US']).get(key, key)


# ===================== DEPENDENCIES CHECK =====================
class Dependencies:
    """Track available optional dependencies"""
    HAS_OSM = False
    HAS_GOOGLE = False
    HAS_RASTERIO = False
    HAS_FFMPEG = False
    
    @staticmethod
    def check_all():
        """Check all optional dependencies"""
        # Check cartopy tiles
        try:
            from cartopy.io.img_tiles import OSM, GoogleTiles
            Dependencies.HAS_OSM = True
            Dependencies.HAS_GOOGLE = True
            logger.info("Cartopy tiles (OSM + Google) available")
        except ImportError as e:
            logger.warning(f"Google tiles unavailable: {e}")
            try:
                from cartopy.io.img_tiles import OSM
                Dependencies.HAS_OSM = True
                logger.info("Cartopy OSM tiles available")
            except ImportError as e:
                logger.warning(f"OSM tiles unavailable: {e}")
        
        # Check rasterio
        try:
            import rasterio
            Dependencies.HAS_RASTERIO = True
            logger.info("Rasterio available for GeoTIFF export")
        except ImportError:
            logger.warning("Rasterio not available - GeoTIFF export disabled")
        
        # Check ffmpeg
        try:
            import matplotlib.animation as animation
            Dependencies.HAS_FFMPEG = animation.writers.is_available('ffmpeg')
            if Dependencies.HAS_FFMPEG:
                logger.info("FFmpeg available for MP4/AVI export")
            else:
                logger.warning("FFmpeg not available - will fallback to GIF")
        except Exception as e:
            logger.warning(f"Could not check FFmpeg: {e}")


# Initialize dependencies check
Dependencies.check_all()

# ===================== USER PREFERENCES =====================
import json
from pathlib import Path

class UserPreferences:
    """Manage user preferences"""
    
    @staticmethod
    def get_preferences_file():
        """Get path to preferences file"""
        # Store in user's home directory
        home = Path.home()
        prefs_dir = home / ".mohid_viewer"
        prefs_dir.mkdir(exist_ok=True)
        return prefs_dir / "preferences.json"
    
    @staticmethod
    def load_preferences():
        """Load user preferences"""
        prefs_file = UserPreferences.get_preferences_file()
        if prefs_file.exists():
            try:
                with open(prefs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load preferences: {e}")
        return {
            'show_welcome': True,
            'last_hdf_path': '',
            'last_export_folder': ''
        }
    
    @staticmethod
    def save_preferences(prefs: dict):
        """Save user preferences"""
        prefs_file = UserPreferences.get_preferences_file()
        try:
            with open(prefs_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save preferences: {e}")
    
    @staticmethod
    def set_show_welcome(show: bool):
        """Set show welcome preference"""
        prefs = UserPreferences.load_preferences()
        prefs['show_welcome'] = show
        UserPreferences.save_preferences(prefs)
    
    @staticmethod
    def should_show_welcome():
        """Check if welcome dialog should be shown"""
        prefs = UserPreferences.load_preferences()
        return prefs.get('show_welcome', True)