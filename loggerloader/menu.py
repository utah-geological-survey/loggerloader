import matplotlib
from typing import Any, Dict, Optional

import json
matplotlib.use("TkAgg")

import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, messagebox, ttk
from pylab import rcParams
import platform

from typing import Any, Dict, Optional
from pathlib import Path

rcParams['figure.figsize'] = 15, 10

import pandas as pd

import __init__
version = __init__.__version__


class ApplicationMenu:
    """Complex menu system with nested menus, recent files tracking, and theme management"""

    def __init__(self, root: tk.Tk, app_instance: Any):
        self.root = root
        self.app = app_instance
        self.menu = tk.Menu(root)
        self.recent_files: list = []
        self.max_recent = 5

        # Load saved settings
        self.settings = self.load_settings()

        # Create main menu structure
        self.create_file_menu()
        self.create_edit_menu()
        self.create_view_menu()
        self.create_tools_menu()
        self.create_help_menu()

        # Apply menu to root
        root.config(menu=self.menu)

    def create_file_menu(self):
        """Create File menu with nested import/export submenus"""
        self.file_menu = tk.Menu(self.menu, tearoff=0)

        # Import submenu
        import_menu = tk.Menu(self.file_menu, tearoff=0)
        import_menu.add_command(label="Well Data...",
                                command=lambda: self.app.import_data('well'))
        import_menu.add_command(label="Barometric Data...",
                                command=lambda: self.app.import_data('baro'))
        import_menu.add_command(label="Manual Measurements...",
                                command=lambda: self.app.import_data('manual'))

        # Export submenu
        export_menu = tk.Menu(self.file_menu, tearoff=0)
        export_menu.add_command(label="Processed Data...",
                                command=lambda: self.app.export_data('processed'))
        export_menu.add_command(label="Charts...",
                                command=lambda: self.app.export_charts())
        export_menu.add_command(label="Report...",
                                command=lambda: self.app.generate_report())

        # Recent files submenu
        self.recent_menu = tk.Menu(self.file_menu, tearoff=0)
        self.update_recent_files()

        # Add all submenus to File menu
        self.file_menu.add_cascade(label="Import", menu=import_menu)
        self.file_menu.add_cascade(label="Export", menu=export_menu)
        self.file_menu.add_separator()
        self.file_menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        self.file_menu.add_separator()
        #self.file_menu.add_command(label="Save Project", command=self.app.save_config)
        #self.file_menu.add_command(label="Save Project As...",
        #                           command=self.app.save_project_as)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.root.quit)

        self.menu.add_cascade(label="File", menu=self.file_menu)

    def create_edit_menu(self):
        """Create Edit menu with data processing options"""
        self.edit_menu = tk.Menu(self.menu, tearoff=0)

        # Data cleaning submenu
        clean_menu = tk.Menu(self.edit_menu, tearoff=0)
        clean_menu.add_command(label="Remove Outliers",
                               command=lambda: self.app.clean_data('outliers'))
        clean_menu.add_command(label="Fix Gaps",
                               command=lambda: self.app.clean_data('gaps'))
        clean_menu.add_command(label="Smooth Data",
                               command=lambda: self.app.clean_data('smooth'))


        self.edit_menu.add_cascade(label="Clean Data", menu=clean_menu)

        self.edit_menu.add_separator()
        self.edit_menu.add_command(label="Preferences...",
                                   command=self.show_preferences)

        self.menu.add_cascade(label="Edit", menu=self.edit_menu)

    def create_view_menu(self):
        """Create View menu with visualization options"""
        self.view_menu = tk.Menu(self.menu, tearoff=0)

        # Theme submenu
        theme_menu = tk.Menu(self.view_menu, tearoff=0)
        theme_menu.add_radiobutton(label="Light",
                                   command=lambda: self.app.set_theme('light'))
        theme_menu.add_radiobutton(label="Dark",
                                   command=lambda: self.app.set_theme('dark'))
        theme_menu.add_radiobutton(label="System",
                                   command=lambda: self.app.set_theme('system'))

        # Chart options submenu
        chart_menu = tk.Menu(self.view_menu, tearoff=0)
        chart_menu.add_checkbutton(label="Show Grid")
        chart_menu.add_checkbutton(label="Show Legend")
        chart_menu.add_separator()
        #chart_menu.add_command(label="Customize...",
        #                       command=self.app.customize_chart)

        self.view_menu.add_cascade(label="Theme", menu=theme_menu)
        self.view_menu.add_cascade(label="Chart Options", menu=chart_menu)
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(label="Status Bar")
        self.view_menu.add_checkbutton(label="Toolbar")

        self.menu.add_cascade(label="View", menu=self.view_menu)

    def create_tools_menu(self):
        """Create Tools menu with analysis options"""
        self.tools_menu = tk.Menu(self.menu, tearoff=0)

        # Analysis submenu
        analysis_menu = tk.Menu(self.tools_menu, tearoff=0)
        analysis_menu.add_command(label="Jump Fix",
                                  command=lambda: self.app.analyze('jump'))

        analysis_menu.add_command(label="Basic Statistics",
                                  command=lambda: self.app.analyze('basic'))
        analysis_menu.add_command(label="Trend Analysis",
                                  command=lambda: self.app.analyze('trend'))
        analysis_menu.add_command(label="Custom Analysis...",
                                  command=lambda: self.app.analyze('custom'))

        self.tools_menu.add_cascade(label="Analysis", menu=analysis_menu)
        #self.tools_menu.add_command(label="Batch Processing...",
        #                            command=self.app.batch_process)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="Options...",
                                    command=self.show_options)

        self.menu.add_cascade(label="Tools", menu=self.tools_menu)

    def create_help_menu(self):
        """Create Help menu with documentation and about"""
        self.help_menu = tk.Menu(self.menu, tearoff=0)

        self.help_menu.add_command(label="Documentation",
                                   command=self.show_documentation)
        self.help_menu.add_command(label="Quick Start Guide",
                                   command=self.show_quickstart)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Check for Updates",
                                   command=self.check_updates)
        self.help_menu.add_command(label="About", command=self.show_about)

        self.menu.add_cascade(label="Help", menu=self.help_menu)

    def update_recent_files(self):
        """Update the recent files menu"""
        self.recent_menu.delete(0, tk.END)

        if not self.recent_files:
            self.recent_menu.add_command(label="(No recent files)", state=tk.DISABLED)
        else:
            for file_path in self.recent_files:
                self.recent_menu.add_command(
                    label=Path(file_path).name,
                    command=lambda f=file_path: self.app.open_recent(f)
                )

            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Clear Recent Files",
                                         command=self.clear_recent_files)

    def add_recent_file(self, file_path: str):
        """Add file to recent files list"""
        if file_path in self.recent_files:
            self.recent_files.remove(file_path)

        self.recent_files.insert(0, file_path)

        if len(self.recent_files) > self.max_recent:
            self.recent_files.pop()

        self.update_recent_files()
        self.save_settings()

    def clear_recent_files(self):
        """Clear the recent files list"""
        self.recent_files.clear()
        self.update_recent_files()
        self.save_settings()

    def load_settings(self) -> Dict:
        """Load saved settings from file"""
        settings_path = Path.home() / '.loggerloader' / 'settings.json'

        if settings_path.exists():
            try:
                with open(settings_path) as f:
                    settings = json.load(f)
                    self.recent_files = settings.get('recent_files', [])
                    return settings
            except:
                return {}
        return {}

    def save_settings(self):
        """Save current settings to file"""
        settings_path = Path.home() / '.loggerloader' / 'settings.json'
        settings_path.parent.mkdir(exist_ok=True)

        settings = {
            'recent_files': self.recent_files,
            'theme': self.settings.get('theme', 'light'),
            'show_toolbar': self.settings.get('show_toolbar', True),
            'show_statusbar': self.settings.get('show_statusbar', True)
        }

        with open(settings_path, 'w') as f:
            json.dump(settings, f)

    def show_preferences(self):
        """Show preferences dialog"""
        # Create preferences dialog window
        prefs = tk.Toplevel(self.root)
        prefs.title("Preferences")
        prefs.geometry("400x300")
        prefs.transient(self.root)
        prefs.grab_set()

        notebook = ttk.Notebook(prefs)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # General settings tab
        general = ttk.Frame(notebook)
        notebook.add(general, text="General")

        # Display settings tab
        display = ttk.Frame(notebook)
        notebook.add(display, text="Display")

        # Add preference controls
        ttk.Button(prefs, text="OK", command=prefs.destroy).pack(pady=5)

    def show_documentation(self):
        """Show documentation in default browser"""
        import webbrowser
        webbrowser.open("https://github.com/utah-geological-survey/loggerloader/wiki")

    def show_quickstart(self):
        """Show quick start guide"""
        messagebox.showinfo("Quick Start Guide",
                            "Quick start guide coming soon!")

    def check_updates(self):
        """Check for software updates"""
        messagebox.showinfo("Updates",
                            "You are running the latest version.")

    def callback(self, url):
        webbrowser.open_new(url)

    def show_about(self):
        """Show about dialog"""
        abwin = tk.Toplevel()
        x = 400
        y = 400
        w = 600
        h = 600
        abwin.geometry('+%d+%d' % (x + w / 2 - 200, y + h / 2 - 200))
        abwin.title('About')
        abwin.transient()
        abwin.grab_set()
        abwin.resizable(width=False, height=False)
        # abwin.configure(background=self.bg)
        # label.grid(row=0, column=0, sticky='ew', padx=4, pady=4)
        pandasver = pd.__version__
        pythonver = platform.python_version()
        mplver = matplotlib.__version__
        ttl = tk.Label(abwin, text=f'Logger Loader v.{version}', font='Helvetica 18 bold')
        ttl.pack()
        # ttl.grid(row=1, column=0, sticky='news', pady=1, padx=4)
        # Import the tcl file
        fm1 = tk.Frame(abwin)
        fm1.pack()
        text1a = 'Processing scripts Written By Paul Inkenbrandt, '
        text1b = 'Utah Geological Survey'
        t1a = tk.Label(fm1, text=text1a)
        t1a.pack(side=tk.LEFT)
        t1b = tk.Label(fm1, text=text1b, fg="blue", cursor="hand2")
        t1b.pack(side=tk.LEFT)
        t1b.bind("<Button-1>", lambda e: self.callback("https://geology.utah.gov"))
        fm2 = tk.Frame(abwin)
        fm2.pack()
        text2a = 'Graphing and Table functions from '
        text2b = 'tksheet by ragardner'
        t2a = tk.Label(fm2, text=text2a)
        t2a.pack(side=tk.LEFT)
        t2b = tk.Label(fm2, text=text2b, fg="blue", cursor="hand2")
        t2b.pack(side=tk.LEFT)
        t2b.bind("<Button-1>", lambda e: self.callback("https://github.com/ragardner/tksheet"))
        fm3ab = tk.Frame(abwin)
        fm3ab.pack()
        text3a = 'UI Themes from '
        text3b = 'Forest-ttk-theme by rdbende'
        t3a = tk.Label(fm3ab, text=text3a)
        t3a.pack(side=tk.LEFT)
        t3b = tk.Label(fm3ab, text=text3b, fg="blue", cursor="hand2")
        t3b.pack(side=tk.LEFT)
        t3b.bind("<Button-1>", lambda e: self.callback("https://github.com/rdbende/Forest-ttk-theme"))

        text3 = 'This program is free software; you can redistribute it and/or\n' \
                + 'modify it under the terms of the GNU General Public License\n' \
                + 'as published by the Free Software Foundation; either version 3\n' \
                + 'of the License, or (at your option) any later version.'
        lic = tk.Label(abwin, text=text3)
        lic.pack()
        text4 = f'Using Python v{pythonver}'
        pyver = tk.Label(abwin, text=text4, fg="blue", cursor="hand2")
        pyver.pack()
        pyver.bind("<Button-1>", lambda e: self.callback("https://www.python.org/"))
        text5 = f'pandas v{pandasver}'
        pdver = tk.Label(abwin, text=text5, fg="blue", cursor="hand2")
        pdver.pack()
        pdver.bind("<Button-1>", lambda e: self.callback("https://pandas.pydata.org/"))
        text6 = f'matplotlib v{mplver}'
        pltver = tk.Label(abwin, text=text6, fg="blue", cursor="hand2")
        pltver.pack()
        pltver.bind("<Button-1>", lambda e: self.callback("https://matplotlib.org/"))
        # tmp.grid(row=2, column=0, sticky='news', pady=1, padx=4)
        return

    def show_options(self):
        """Show options dialog"""
        # Create options dialog window
        options = tk.Toplevel(self.root)
        options.title("Options")
        options.geometry("500x400")
        options.transient(self.root)
        options.grab_set()

        notebook = ttk.Notebook(options)
        notebook.pack(fill='both', expand=True, padx=5, pady=5)

        # Processing options tab
        processing = ttk.Frame(notebook)
        notebook.add(processing, text="Processing")

        # Analysis options tab
        analysis = ttk.Frame(notebook)
        notebook.add(analysis, text="Analysis")

        # Export options tab
        export = ttk.Frame(notebook)
        notebook.add(export, text="Export")

        # Add options controls
        ttk.Button(options, text="OK", command=options.destroy).pack(pady=5)
