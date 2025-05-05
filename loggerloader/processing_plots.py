import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
import random
from plotly.offline import iplot
from plotly.subplots import make_subplots



def manual_vs_transducer(manual_data, corrected_wl, siteid):
    '''plot manual measurements for dtwbelowcasing versus corrected_wl data
    data taken directly from loggerloader output
    '''
    fig, ax = plt.subplots(figsize=(10, 6))  # Optional: specify a figure size

    # Plotting water elevation
    ax.plot(manual_data.index, manual_data['dtwbelowcasing'], marker='o', linestyle=None,label='Depth to Water from Manual', color='blue')
    ax.set_xlabel('Reading Date')  # X-axis label
    ax.set_ylabel('Depth to water below casing')  # Y-axis label for the first plot

    # Creating a secondary axis for corrected water pressure
    ax2 = ax.twinx()
    ax2.plot(corrected_wl.index, corrected_wl['corrwl'], color='red', label='Feet of water above transducer')
    ax2.set_ylabel('Feet of water above transducer')  # Y-axis label for the second plot

    plt.title(siteid)
    ax.legend(loc='upper left', bbox_to_anchor=(0.1, 0.9))  # Adjust legend position
    ax2.legend(loc='upper left', bbox_to_anchor=(0.1, 0.95))  # Adjust legend position
    plt.tight_layout()



def manual_vs_transducer_plotly(manual_data, well_data, siteid, corrected=True):
    '''plot manual measurements for dtwbelowcasing versus corrected_wl data
    data taken directly from loggerloader output
    plotly version of the above
    '''
    # Create the figure
    fig = go.Figure()

    if corrected == True:
        field_name ='corrwl'
    else:
        field_name = 'Level'

    # Plotting water elevation (Depth to Water from Manual)
    fig.add_trace(go.Scatter(x=manual_data.index, 
                             y=manual_data['dtwbelowcasing'], 
                             mode='markers', 
                             name='Depth to Water from Manual', 
                             line=dict(color='blue')))
    
    # Plotting corrected water pressure (Feet of water above transducer)
    fig.add_trace(go.Scatter(x=well_data.index, 
                             y=well_data[field_name], 
                             mode='lines', 
                             name='Feet of water above transducer or raw water level reading', 
                             line=dict(color='red'), 
                             yaxis="y2"))
    
    # Create axis labels and title
    fig.update_layout(
        title=siteid,
        xaxis_title='Reading Date',
        yaxis_title='Depth to water below casing',
        yaxis2=dict(
            title='Feet of water above transducer or raw water level reading',
            overlaying='y',
            side='right'
        ),
        legend=dict(x=0.1, y=0.9),
        template="plotly",
        height=600
    )

    # Show the plot
    fig.show()

def stickup_plot(plot_data, locationid):
    '''plot of stickup height over time
    '''
    fig, ax = plt.subplots(figsize=(10, 3)) 
    ax.scatter(plot_data.index, plot_data.current_stickup_height, s=10, color='blue')  # Scatter plot
    ax.plot(plot_data.index, plot_data.current_stickup_height, color='black', lw=0.5, ls='--')  # Scatter plot
    ax.set_xlabel('Reading Date')  # X-axis label
    ax.set_ylabel('Current Stickup Height')  # Y-axis label for the first plot
    plt.title(f"{locationid}")


def processed_vs_manual(siteid, processed_data, manual_data, plot_field='waterelevation'):
    '''Plot of processed transducer data versus manual transducer data, using a common
    field in both datasets. Plot will be titled with the siteid
    THIS MIGHT JUST DO THE SAME THING AS manual_vs_transducer_plotly
    '''
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=processed_data.index, y=processed_data[plot_field], 
                             mode='lines', name='Processed Data', 
                             line=dict(color='red', width=2)))
    fig.add_trace(go.Scatter(x=manual_data.index, y=manual_data[plot_field], 
                             mode='markers', name='Manual Measurement', 
                             marker=dict(color='blue')))
    fig.update_layout(
        title=siteid,
        xaxis_title='Reading Date',
        yaxis_title=f'{plot_field} (ft)',
        legend=dict(x=0, y=1, traceorder='normal', orientation='h', xanchor='left', yanchor='bottom'),
        margin=dict(t=50, b=50, l=50, r=50)
    )
    fig.show()


def plotlystuff(datasets, colnames, chrttypes=None, datatitles=None, chrttitle='well', colors=None,
                two_yaxes=False, axisdesig=None, axislabels=['Levels', 'Barometric Pressure'], opac=None, 
                plot_height=300):
    '''Plots one or more datasets on a shared set of axes
    '''
    
    if chrttypes is None:
        chrttypes = ['lines'] * len(datasets)

    if opac is None:
        opac = [0.8] * len(datasets)
        
    if datatitles is None:
        datatitles = colnames
    
    if axisdesig is None:
        axisdesig = ['y1'] * len(datasets)
        
    if colors is None:
        if len(datasets) <= 5: 
            colors = ['#228B22', '#FF1493', '#F7DC6F', '#663399', '#FF0000']
        else:
            colors = []
            for i in range(len(datasets)):
                colors.append('#{:02x}{:02x}{:02x}'.format(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
    
    modetypes = ['markers', 'lines+markers', 'lines']
    datum = {}
    
    # Plotting the line charts for the datasets
    for i in range(len(datasets)):
        datum['d' + str(i)] = go.Scatter(
            x=datasets[i].index,
            y=datasets[i][colnames[i]],
            name=datatitles[i],
            line=dict(color=colors[i]),
            mode=chrttypes[i],
            opacity=opac[i],
            yaxis=axisdesig[i]
        )
    
    # Combine the data for plotting
    data = list(datum.values())

    # Calculate dynamic y-axis range
    y_min = min([datasets[i][colnames[i]].min() for i in range(len(datasets))])
    y_max = max([datasets[i][colnames[i]].max() for i in range(len(datasets))])
    
    # Layout definition with adjustments for vertical space and axis range
    layout = dict(
        title=chrttitle,
        xaxis=dict(
            rangeslider=dict(visible=True),
            type='date',
            tickformat='%Y-%m-%d %H:%M'
        ),
        yaxis=dict(
            title=axislabels[0],
            titlefont=dict(color='#1f77b4'),
            tickfont=dict(color='#1f77b4'),
            range=[y_min, y_max]  # Set dynamic y-axis range
        ),
        height=plot_height,  # Increase the height for more vertical space
        margin=dict(t=50, b=50, l=60, r=60)  # Adjust margins
    )
    
    if two_yaxes:
        layout['yaxis2'] = dict(
            title=axislabels[1],
            titlefont=dict(color='#ff7f0e'),
            tickfont=dict(color='#ff7f0e'),
            anchor='x',
            overlaying='y',
            side='right',
            position=0.15
        )

    fig = dict(data=data, layout=layout)
    iplot(fig, filename='well')
    return
