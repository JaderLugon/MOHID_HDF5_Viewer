"""
MOHID HDF5 Viewer - JPG Series Viewer
Disk-based viewer for exported JPG time series
"""
import os
import re
from typing import List, Tuple, Optional

import matplotlib.pyplot as plt
import FreeSimpleGUI as sg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import logger, FilePatterns, UIConfig


class JpgSeriesViewer:
    """
    Viewer for JPG time series stored on disk.
    
    Loads images on-demand for memory efficiency.
    """
    
    def __init__(self):
        self.entries: List[Tuple[str, str]] = []  # (timestamp, filepath)
        self.idx: int = 0
        self.fig: Optional[plt.Figure] = None
        self.ax: Optional[plt.Axes] = None
        self.im_artist: Optional[plt.AxesImage] = None
        self.fig_canvas: Optional[FigureCanvasTkAgg] = None
    
    @staticmethod
    def extract_timestamp(filepath: str) -> str:
        """
        Extract timestamp from JPG filename.
        
        Args:
            filepath: Path to JPG file
            
        Returns:
            Timestamp string or filename without extension
        """
        basename = os.path.basename(filepath)
        
        # Try to match timestamp pattern
        match = re.search(FilePatterns.TIMESTAMP_PATTERN, basename, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Fallback to filename without extension
        return os.path.splitext(basename)[0]
    
    def load_from_directory(self, folder: str) -> None:
        """
        Load JPG file list from directory.
        
        Args:
            folder: Directory containing JPG files
            
        Raises:
            RuntimeError: If no JPG files found
        """
        if not os.path.isdir(folder):
            raise RuntimeError(f"Directory not found: {folder}")
        
        jpg_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith('.jpg')
        ]
        
        if not jpg_files:
            raise RuntimeError("No JPG files found in selected folder")
        
        # Build list with timestamps
        records = [(self.extract_timestamp(path), path) for path in jpg_files]
        
        # Sort by timestamp
        records.sort(key=lambda x: x[0])
        
        self.entries = records
        self.idx = 0
        
        logger.info(f"Loaded {len(self.entries)} JPG files from {folder}")
    
    def _create_figure(self) -> Tuple[plt.Figure, plt.Axes]:
        """
        Create matplotlib figure for displaying images.
        
        Returns:
            Tuple of (figure, axes)
        """
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_axes([0.01, 0.01, 0.98, 0.98])
        ax.axis('off')
        return fig, ax
    
    def mount(self, tk_canvas, index: int = 0) -> None:
        """
        Mount viewer to Tkinter canvas.
        
        Args:
            tk_canvas: Tkinter canvas widget
            index: Initial frame index
        """
        # Clean up existing canvas
        if self.fig_canvas is not None:
            try:
                widget = self.fig_canvas.get_tk_widget()
                widget.pack_forget()
                widget.destroy()
            except Exception as e:
                logger.warning(f"Error cleaning up canvas: {e}")
        
        # Close old figures
        plt.close('all')
        
        # Create new figure
        self.fig, self.ax = self._create_figure()
        
        # Create Tk canvas
        self.fig_canvas = FigureCanvasTkAgg(self.fig, master=tk_canvas)
        self.fig_canvas.draw()
        self.fig_canvas.get_tk_widget().pack(side='top', fill='both', expand=1)
        
        # Show initial frame
        self.show(index)
    
    def show(self, index: int) -> None:
        """
        Display frame at given index.
        
        Args:
            index: Frame index (will be clamped to valid range)
        """
        # Clamp index
        index = max(0, min(index, len(self.entries) - 1))
        
        timestamp, path = self.entries[index]
        
        try:
            # Lazy load image
            img = plt.imread(path)
            
            # Update or create image artist
            if self.im_artist is None:
                self.im_artist = self.ax.imshow(img)
            else:
                self.im_artist.set_data(img)
            
            # Redraw
            try:
                self.fig.canvas.draw_idle()
            except Exception:
                self.fig.canvas.draw()
            
            self.idx = index
            
        except Exception as e:
            logger.error(f"Error displaying frame {index}: {e}")
    
    def timestamps(self) -> List[str]:
        """Get list of all timestamps"""
        return [ts for ts, _ in self.entries]
    
    def count(self) -> int:
        """Get total number of frames"""
        return len(self.entries)


def make_viewer_window(
    nframes: int,
    timestamps: List[str]
) -> sg.Window:
    """
    Create viewer window GUI.
    
    Args:
        nframes: Total number of frames
        timestamps: List of timestamp strings
        
    Returns:
        PySimpleGUI Window
    """
    layout = [
        [sg.Text(
            'Time Series Viewer (JPG from disk)',
            justification='center',
            expand_x=True
        )],
        [
            sg.Text('Timestamp:'),
            sg.Combo(
                timestamps,
                key='-V_TS-',
                size=(24, 1),
                enable_events=True
            ),
            sg.Button('Go', key='-V_GO-'),
            sg.Push(),
            sg.Button('Maximize/Restore', key='-V_MAX-')
        ],
        [sg.Canvas(key='-VCANVAS-', expand_x=True, expand_y=True)],
        [
            sg.Button('<< Prev', key='-V_PREV-'),
            sg.Slider(
                range=(0, max(0, nframes - 1)),
                default_value=0,
                resolution=1,
                orientation='h',
                size=(50, 15),
                key='-V_SLIDER-',
                enable_events=True,
                expand_x=True
            ),
            sg.Button('Next >>', key='-V_NEXT-'),
            sg.Text(
                f"0 / {max(1, nframes)}",
                key='-V_IDX-',
                size=(14, 1)
            )
        ],
        [sg.Button('Close', key='-V_CLOSE-')]
    ]
    
    return sg.Window(
        'Time Series Viewer',
        layout,
        finalize=True,
        font=UIConfig.DEFAULT_FONT,
        location=UIConfig.VIEWER_WINDOW_LOCATION,
        resizable=True
    )


def open_viewer_window(folder: str) -> Tuple[Optional[sg.Window], Optional[JpgSeriesViewer]]:
    """
    Open viewer window for a JPG folder.
    
    Args:
        folder: Path to folder containing JPG files
        
    Returns:
        Tuple of (window, viewer) or (None, None) on error
    """
    try:
        # Create viewer and load files
        viewer = JpgSeriesViewer()
        viewer.load_from_directory(folder)
        
        # Create window
        timestamps = viewer.timestamps()
        window = make_viewer_window(viewer.count(), timestamps)
        
        # Set initial timestamp
        if timestamps:
            window['-V_TS-'].update(value=timestamps[0])
        
        # Mount viewer to canvas
        viewer.mount(window['-VCANVAS-'].TKCanvas, 0)
        
        # Update index display
        window['-V_IDX-'].update(f"1 / {viewer.count()}")
        
        return window, viewer
        
    except Exception as e:
        logger.error(f"Error opening viewer: {e}")
        sg.popup_error(f"Error opening viewer: {e}")
        return None, None