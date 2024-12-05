import tkinter as tk
from tkinter import ttk
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import tempfile
import webbrowser

class PlotlyTkinterWidget:
    """A widget for embedding Plotly plots in Tkinter applications"""
    
    def __init__(self, master, height=600):
        """
        Initialize the Plotly widget
        
        Args:
            master: Parent Tkinter widget
            height: Height of the plot in pixels
        """
        self.master = master
        self.height = height
        self.temp_dir = tempfile.mkdtemp()
        self.current_html = None
        
        # Create main frame
        self.frame = ttk.Frame(master)
        self.frame.pack(fill=tk.BOTH, expand=True)
        
        # Create toolbar
        self.create_toolbar()
        
        # Create display frame
        self.display_frame = ttk.Frame(self.frame)
        self.display_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create label for plot display
        self.plot_label = ttk.Label(
            self.display_frame,
            text="Click 'Show Plot' to view visualization",
            justify=tk.CENTER
        )
        self.plot_label.pack(expand=True)
        
        # Store current figure
        self.current_fig = None
        
    def create_toolbar(self):
        """Create toolbar with plot controls"""
        self.toolbar = ttk.Frame(self.frame)
        self.toolbar.pack(fill=tk.X, padx=5, pady=2)
        
        # Show plot button
        self.show_btn = ttk.Button(
            self.toolbar, 
            text="Show Plot",
            command=self.show_plot
        )
        self.show_btn.pack(side=tk.LEFT, padx=2)
        
        # Export button
        self.export_btn = ttk.Button(
            self.toolbar, 
            text="Export Plot",
            command=self.export_plot
        )
        self.export_btn.pack(side=tk.LEFT, padx=2)
        
        # Plot type selector
        self.plot_type = tk.StringVar(value='line')
        plot_types = ['line', 'scatter', 'bar']
        self.plot_selector = ttk.Combobox(
            self.toolbar,
            textvariable=self.plot_type,
            values=plot_types,
            state='readonly',
            width=10
        )
        self.plot_selector.pack(side=tk.LEFT, padx=2)
        self.plot_selector.bind('<<ComboboxSelected>>', self.on_plot_type_change)
        
    def plot_water_levels(self, data, well_field='Level'):
        """
        Plot water level data with well, barometric and corrected levels
        
        Args:
            data: DataFrame with water level data
            well_field: Name of well level column
            baro_field: Name of barometric level column 
            corrected_field: Name of corrected level column
        """
        # Create figure with secondary y-axis
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Add well level
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[well_field],
                name="Well Level",
                line=dict(color='blue')
            ),
            secondary_y=False
        )

            
        # Update layout
        fig.update_layout(
            title="Water Level Data",
            xaxis_title="Date",
            yaxis_title="Well Level (ft)",
            hovermode='x unified',
            showlegend=True,
            height=self.height
        )
        
        self.update_plot(fig)
        
    def plot_manual_measurements(self, data, auto_data=None, 
                               manual_field='dtwbelowcasing',
                               auto_field='Level'):
        """
        Plot manual measurements with optional automated measurements
        
        Args:
            data: DataFrame with manual measurements
            auto_data: Optional DataFrame with automated measurements
            manual_field: Name of manual measurement column
            auto_field: Name of automated measurement column
        """
        fig = go.Figure()
        
        # Plot manual measurements as scatter points
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[manual_field],
                mode='markers',
                name='Manual Measurements',
                marker=dict(
                    size=8,
                    color='red',
                    symbol='circle'
                )
            )
        )
        
        # Add automated measurements if available
        if auto_data is not None:
            fig.add_trace(
                go.Scatter(
                    x=auto_data.index,
                    y=auto_data[auto_field],
                    mode='lines',
                    name='Automated Measurements',
                    line=dict(color='blue')
                )
            )
            
        # Update layout
        fig.update_layout(
            title="Manual vs Automated Measurements",
            xaxis_title="Date",
            yaxis_title="Water Level (ft)",
            hovermode='x unified',
            height=self.height
        )
        
        self.update_plot(fig)
        
    def plot_drift_correction(self, data, original='Level', 
                            corrected='corrwl', drift='driftcorrection'):
        """
        Plot drift correction analysis
        
        Args:
            data: DataFrame with drift correction data
            original: Name of original measurement column
            corrected: Name of corrected measurement column
            drift: Name of drift correction column
        """
        fig = make_subplots(rows=2, cols=1, 
                           shared_xaxes=True,
                           vertical_spacing=0.1,
                           subplot_titles=("Water Levels", "Drift Correction"))
        
        # Plot water levels
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[original],
                name="Original",
                line=dict(color='red')
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[corrected],
                name="Corrected",
                line=dict(color='blue')
            ),
            row=1, col=1
        )
        
        # Plot drift correction
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[drift],
                name="Drift",
                line=dict(color='green')
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            height=800,
            showlegend=True,
            hovermode='x unified'
        )
        
        self.update_plot(fig)
        
    def update_plot(self, fig):
        """Update the current plot"""
        self.current_fig = fig
        
        # Save to temporary HTML file
        if self.current_html:
            try:
                os.remove(self.current_html)
            except:
                pass
                
        temp_path = os.path.join(self.temp_dir, f'plot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html')
        fig.write_html(
            temp_path,
            include_plotlyjs=True,
            full_html=True,
            config={'responsive': True}
        )
        self.current_html = temp_path
        
        # Update label
        self.plot_label.config(text="Plot updated - click 'Show Plot' to view")
        
    def show_plot(self):
        """Show the current plot in default browser"""
        if self.current_html and os.path.exists(self.current_html):
            webbrowser.open(f'file://{self.current_html}')
        
    def export_plot(self):
        """Export current plot"""
        if self.current_fig is None:
            return
            
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[
                ("HTML files", "*.html"),
                ("PNG files", "*.png"),
                ("PDF files", "*.pdf")
            ]
        )
            
        if not filename:
            return
            
        # Export based on file extension
        ext = filename.split('.')[-1].lower()
        if ext == 'html':
            self.current_fig.write_html(filename)
        elif ext == 'png':
            self.current_fig.write_image(filename)
        elif ext == 'pdf':
            self.current_fig.write_image(filename)
            
    def on_plot_type_change(self, event=None):
        """Handle plot type changes"""
        if self.current_fig is not None:
            # Update plot type while maintaining data
            plot_type = self.plot_type.get()
            for trace in self.current_fig.data:
                if plot_type == 'line':
                    trace.mode = 'lines'
                elif plot_type == 'scatter':
                    trace.mode = 'markers'
                elif plot_type == 'bar':
                    # Convert to bar chart
                    new_trace = go.Bar(
                        x=trace.x,
                        y=trace.y,
                        name=trace.name
                    )
                    trace.update(new_trace)
                    
            self.update_plot(self.current_fig)
            
    def destroy(self):
        """Clean up resources"""
        # Remove temporary files
        if self.current_html and os.path.exists(self.current_html):
            try:
                os.remove(self.current_html)
            except:
                pass
        if os.path.exists(self.temp_dir):
            try:
                os.rmdir(self.temp_dir)
            except:
                pass
        self.frame.destroy()
