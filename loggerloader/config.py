import matplotlib
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
import json
matplotlib.use("TkAgg")

from pylab import rcParams
import platform
import logging

from pathlib import Path
from datetime import datetime

@dataclass
class ProcessingSettings:
    """Settings for data processing"""
    sampling_interval: int = 60  # minutes
    max_gap: int = 120  # minutes
    outlier_threshold: float = 3.0  # standard deviations
    smoothing_window: int = 3  # measurements
    drift_tolerance: float = 0.3  # ft/day
    interpolation_limit: int = 90  # minutes

    def validate(self) -> bool:
        """Validate processing settings"""
        valid_interval = 0 < self.sampling_interval <= 1440
        valid_gap = self.max_gap >= self.sampling_interval
        valid_outlier = self.outlier_threshold > 0
        valid_window = self.smoothing_window > 0
        valid_drift = self.drift_tolerance > 0
        valid_interp = self.interpolation_limit > 0
        return all([valid_interval, valid_gap, valid_outlier,
                    valid_window, valid_drift, valid_interp])


@dataclass
class DisplaySettings:
    """Settings for data display"""
    theme: str = "forest-light"  # light, dark
    sheet_theme: str = 'light blue'  # light blue, dark green
    default_chart_type: str = 'line'  # line, scatter, both
    show_statistics: bool = True
    show_toolbar: bool = True
    auto_refresh: bool = True
    date_format: str = '%Y-%m-%d %H:%M'

    def validate(self) -> bool:
        """Validate display settings"""
        valid_theme = self.theme in ["forest-light", "forest-dark"]
        valid_sheet = self.sheet_theme in ['light blue', 'dark green']
        valid_chart = self.default_chart_type in ['line', 'scatter', 'both']
        return all([valid_theme, valid_sheet, valid_chart])

class Configuration:
    """Manages application configuration settings"""

    def __init__(self):
        """Initialize configuration manager"""
        self.logger = logging.getLogger('LoggerLoader.Config')

        # Set up configuration paths
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / 'config.json'
        self.plugin_dir = self.config_dir / 'plugins'

        # Initialize settings
        self.processing = ProcessingSettings()
        self.display = DisplaySettings()

        # Track recent files and directories
        self.recent_files: Dict[str, str] = {}
        self.default_dirs: Dict[str, str] = {}

        # Load or create configuration
        self._ensure_config_exists()
        self.load_config()

    def _get_config_dir(self) -> Path:
        """Get configuration directory based on platform"""
        home = Path.home()

        if platform.system() == 'Windows':
            config_dir = home / 'AppData' / 'Local' / 'LoggerLoader'
        elif platform.system() == 'Darwin':
            config_dir = home / 'Library' / 'Application Support' / 'LoggerLoader'
        else:
            config_dir = home / '.loggerloader'

        return config_dir

    def _ensure_config_exists(self):
        """Ensure configuration directory and files exist"""
        try:
            # Create directories if needed
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.plugin_dir.mkdir(exist_ok=True)

            # Create default config if needed
            if not self.config_file.exists():
                self.save_config()

        except Exception as e:
            self.logger.error(f"Error creating config structure: {str(e)}")
            raise

    def load_config(self):
        """Load configuration from file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)

                # Load section settings
                if 'processing' in config_data:
                    self.processing = ProcessingSettings(**config_data['processing'])
                if 'display' in config_data:
                    self.display = DisplaySettings(**config_data['display'])

                # Load recent files and directories
                self.recent_files = config_data.get('recent_files', {})
                self.default_dirs = config_data.get('default_dirs', {})

                self.logger.info("Configuration loaded successfully")

        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            # Fall back to defaults
            self.reset_to_defaults()

    def save_config(self):
        """Save current configuration to file"""
        try:
            config_data = {
                'processing': asdict(self.processing),
                'display': asdict(self.display),
                'recent_files': self.recent_files,
                'default_dirs': self.default_dirs,
                'last_modified': datetime.now().isoformat()
            }

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)

            self.logger.info("Configuration saved successfully")

        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            raise

    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.processing = ProcessingSettings()
        self.display = DisplaySettings()
        self.recent_files = {}
        self.default_dirs = {}

        self.save_config()
        self.logger.info("Configuration reset to defaults")

    def validate(self) -> bool:
        """Validate all configuration settings"""
        try:
            valid_units = self.units.validate()
            valid_processing = self.processing.validate()
            valid_display = self.display.validate()

            return all([valid_units, valid_processing, valid_display])

        except Exception as e:
            self.logger.error(f"Configuration validation error: {str(e)}")
            return False

    def add_recent_file(self, file_type: str, file_path: str, max_recent: int = 10):
        """Add a file to recent files list"""
        if file_type not in self.recent_files:
            self.recent_files[file_type] = []

        # Remove if already exists
        if file_path in self.recent_files[file_type]:
            self.recent_files[file_type].remove(file_path)

        # Add to front of list
        self.recent_files[file_type].insert(0, file_path)

        # Trim list if needed
        self.recent_files[file_type] = self.recent_files[file_type][:max_recent]

        self.save_config()

    def set_default_dir(self, dir_type: str, dir_path: str):
        """Set default directory for a file type"""
        self.default_dirs[dir_type] = dir_path
        self.save_config()

    def get_default_dir(self, dir_type: str) -> str:
        """Get default directory for a file type"""
        return self.default_dirs.get(dir_type, str(Path.home()))

    def export_config(self, file_path: str):
        """Export configuration to file"""
        try:
            with open(file_path, 'w') as f:
                json.dump({
                    'processing': asdict(self.processing),
                    'display': asdict(self.display)
                }, f, indent=4)
            self.logger.info(f"Configuration exported to {file_path}")

        except Exception as e:
            self.logger.error(f"Error exporting configuration: {str(e)}")
            raise

    def import_config(self, file_path: str):
        """Import configuration from file"""
        try:
            with open(file_path, 'r') as f:
                config_data = json.load(f)

            # Validate imported data
            if all([
                isinstance(config_data.get('processing'), dict),
                isinstance(config_data.get('display'), dict)
            ]):
                self.processing = ProcessingSettings(**config_data['processing'])
                self.display = DisplaySettings(**config_data['display'])

                if self.validate():
                    self.save_config()
                    self.logger.info(f"Configuration imported from {file_path}")
                else:
                    raise ValueError("Invalid configuration values")
            else:
                raise ValueError("Invalid configuration format")

        except Exception as e:
            self.logger.error(f"Error importing configuration: {str(e)}")
            raise
