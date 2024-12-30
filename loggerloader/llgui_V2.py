import matplotlib
import pandas as pd
from typing import Any, Dict, Optional
from tksheet import Sheet
from dataclasses import dataclass, asdict
import json
matplotlib.use("TkAgg")


import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, messagebox, ttk


from pylab import rcParams


import logging

#try:
from loader import jumpfix
from views import ViewManager
from menu import ApplicationMenu
#except:
    #from .loader import NewTransImp, drop_duplicates_keep_max_by_field, jumpfix
    #from .plotly_tk_vis import PlotlyTkinterWidget


try:
    import pyi_splash

    # Update the text on the splash screen
    pyi_splash.update_text("PyInstaller is a great software!")
    pyi_splash.update_text("Second time's a charm!")

    # Close the splash screen. It does not matter when the call
    # to this function is made, the splash screen remains open until
    # this function is called or the Python program is terminated.
    pyi_splash.close()
except:
    pass


rcParams['figure.figsize'] = 15, 10


class DataModel:
    """Handles data storage and manipulation"""

    def __init__(self):
        self.data: pd.DataFrame = None
        self.well_data: pd.DataFrame = None
        self.baro_data: pd.DataFrame = None
        self.datatable = {}
        self.bcombo = {}
        self.locidmatch = {}
        self.bulktransfilestr = {}
        self.beg_end = {}

    def store_data(self, data):
        """Store data with given key"""
        self.data = data

    def get_data(self):
        """Retrieve data for given key"""
        return self.data

    def clear_data(self):
        """Clear data for given key"""
        if self.data:
            del self.data


class LoggerLoaderApp:
    """Main application class"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Logger Loader")
        self.root.geometry("1400x800")

        # Initialize components
        self.data_model = DataModel()
        self.view_manager = ViewManager(self.root, self.data_model)
        self.view_manager.set_styles()

        # Create interface
        self.menu = ApplicationMenu(self.root, self)
        #self.create_menu()
        self.view_manager.create_main_interface()

        # Set up logging
        self.setup_logging()


    def setup_logging(self):
        """Set up application logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('LoggerLoader')

    def run(self):
        """Start the application"""
        self.root.mainloop()

def main():
    root = tk.Tk()
    feedback = LoggerLoaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    app = LoggerLoaderApp()
    app.run()




