import os
from datetime import datetime
from pytz import timezone

import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from dash.dependencies import Input, Output
import psycopg2

#################
# Database stuff
#################

meta_db = "'meta'"
rds_db_user = "'arsegorovDB'"
rds_host = "'metainstance.cagix2mfixd1.us-east-1.rds.amazonaws.com'"
password = os.environ.get('PGPASSWORD')

xml_log_table = 'xml_log'
time_field = 'date_time_utc'
file_field = 'file'
status_field = 'status'
msgs_field = 'messages'

##############
# Plot stuff
##############

colors = {
    -1: 'lightgray',
    0: 'green',
    1: 'red',
    2: 'orange'
}

status = {
    -1: 'Missing Data',
    0: 'Processing Finished',
    1: 'Processing Failed',
    2: 'Currently Processing'
}

refresh_rate = 10  # in seconds

# Initializing the plot
upload_status = []

for i in range(24):
    for j in range(60):
        upload_status.append([i, j, -1])

current_date = datetime.now(timezone('US/Eastern')).date()


def graph():
    return {
        'data': [
            go.Scatter(
                x=[
                    x[1]
                    for x in upload_status if x[2] == i
                ],
                y=[
                    x[0]
                    for x in upload_status if x[2] == i
                ],
                hovertext=[
                    '{:0>2}:{:0>2} {}'.format(x[0], x[1], status[i])
                    for x in upload_status if x[2] == i
                ],
                hoverinfo='text',
                mode='markers',
                opacity=0.8,
                marker={
                    'symbol': 'square',
                    'size': 7,
                    'line': {'width': 0.5, 'color': '#333'},
                    'color': colors[i]
                },
                name=status[i]
            ) for i in range(-1, 3, 1)
        ],
        'layout': go.Layout(
            xaxis={
                'title': 'Minutes',
                'tickmode': 'array',
                'tickvals': [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                'tickfont': {'color': 'black'},
                'color': 'gray',
                'gridcolor': 'lightgray',
                'zeroline': False
            },
            yaxis={
                'title': 'Hours',
                'tickmode': 'array',
                'tickvals': [0, 6, 12, 18],
                'tickfont': {'color': 'black'},
                'color': 'gray',
                'gridcolor': 'lightgray',
                'zeroline': False
            },
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': -0.2},
            hovermode='closest'
        )
    }


##############
# Dash layout
##############

app = dash.Dash()
app.title = u'Data Freeway, an Insight Demo Project'

app.layout = html.Div(
    style={'font-family': 'sans-serif'},
    children=[
        dcc.Location(id='url', refresh=False),

        html.H1(
            children='Processing Status',
            style={
                'textAlign': 'center'
            }
        ),

        html.Div(
            children=[
                html.Label(
                    htmlFor='date',
                    children='Select a date to see the status for that day: '
                ),

                dcc.Input(
                    id='date',
                    type='date',
                    value=current_date
                )
            ],
            style={
                'font-family': 'sans-serif'
            }
        ),

        html.P(
            children='The markers on the graph correspond to the minutes in 24 hours of the day.'
                     ' Click on a marker for more details.'
        ),

        dcc.Graph(
            id='upload-status',
            figure=graph()
        ),

        html.P(
            children='Latest log message: '
        ),

        html.Pre(
            id='log-message',
            style={
                'border': 'this lightgrey solid',
                'overflowX': 'scroll'
            }
        ),

        dcc.Interval(
            id='interval-component',
            interval=refresh_rate * 1000,  # in milliseconds
            n_intervals=0
        )
    ])

db_connection_string = "dbname={} ".format(meta_db) \
                       + "user={} ".format(rds_db_user) \
                       + "host={} ".format(rds_host) \
                       + "password='{}'".format(password)


@app.callback(
    output=Output('upload-status', 'figure'),
    inputs=[Input('date', 'value'), Input('interval-component', 'n_intervals')]
)
def show_date_status(date, n):
    global upload_status, current_date

    current_date = date

    upload_status = []
    for i in range(24):
        for j in range(60):
            upload_status.append([i, j, -1])

    print('Date: {}'.format(date))
    connection = psycopg2.connect(db_connection_string)
    cur = connection.cursor()

    file = "split_part({}, '.', 1)".format(file_field)

    last_log_entry_time = "(SELECT max({0}) AS time, file " \
                          " FROM (SELECT {0}, {1} AS file from {2}) AS sub " \
                          " GROUP BY file)".format(time_field, file,
                                                   xml_log_table)

    query = "SELECT t1.{0}, t1.{1} " \
            "FROM " \
            " {2} AS t JOIN {3} AS t1 " \
            " ON t.time = t1.{4} AND t.file = split_part(t1.{0}, '.', 1) " \
            "WHERE t.file LIKE 'Traf%ic/{5}/%Trafficspeed';".format(file_field, status_field,
                                                                   last_log_entry_time, xml_log_table,
                                                                   time_field,
                                                                   current_date)

    cur.execute(query)
    rows = cur.fetchall()
    connection.close()

    for row in rows:
        time = row[0].split('/')[2][:4]
        stat = row[1]
        hour, minute = int(time[:2]), int(time[2:])
        upload_status[hour * 60 + minute] = [hour, minute, stat]

    return graph()


@app.callback(
    output=Output('log-message', 'children'),
    inputs=[Input('upload-status', 'clickData')]
)
def show_log(click_data):
    if click_data is None:
        return ''

    point = click_data['points'][0]
    minute = point['x']
    hour = point['y']

    connection = psycopg2.connect(db_connection_string)
    cur = connection.cursor()

    file = "split_part({}, '.', 1)".format(file_field)

    last_message = "CASE " \
                   "  WHEN array_length({0}, 1) > 0 THEN {0}[array_length({0}, 1)] " \
                   "  ELSE '' " \
                   "END".format(msgs_field)

    last_log_entry = "SELECT max({0}) AS time, {1}, {2} AS file " \
                     "FROM xml_log " \
                     "GROUP BY {1}, file".format(time_field, msgs_field, file)

    query = "SELECT ({}) AS message " \
            "FROM ({}) AS t " \
            "WHERE file LIKE 'Traf%ic/{}/{:0>2}{:0>2}%Trafficspeed' " \
            "ORDER BY time DESC " \
            "LIMIT 1;".format(last_message, last_log_entry,
                              current_date, hour, minute)

    cur.execute(query)
    rows = cur.fetchall()
    connection.close()

    if len(rows) == 0:
        return ''

    message = rows[0][0]
    return message


if __name__ == '__main__':
    app.run_server(
        host='0.0.0.0'
    )
