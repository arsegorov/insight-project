import os
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

##############
# Graph stuff
##############

colors = {
    -1: 'white',
    0: 'green',
    1: 'red',
    2: 'orange'
}

status = {
    -1: 'Missing',
    0: 'Succeeded',
    1: 'Failed',
    2: 'Processing'
}

# Initializing the plot
upload_status = []

for i in range(24):
    for j in range(60):
        upload_status.append([i, j, -1])

##############
# Dash layout
##############

app = dash.Dash()

app.layout = html.Div(
    style={'font-family': 'sans-serif'},
    children=[
        html.H1(
            children='Traffic Data Processing Status',
            style={
                'textAlign': 'center'
            }
        ),

        html.P(
            children='This page displays the processing status for the minute-by-minute data files for a given day. '
                     'The file with the data recorded at HH hours MM minutes is represented by a point on the graph. '
                     'The hours are on the vertical axis, and the minutes are on the horizontal axis.',
            style={
                'font-family': 'sans-serif'
            }
        ),

        html.Div(
            children=[
                html.Label(
                    htmlFor='date',
                    children='Select a day to see the processing status for that day: '
                ),

                dcc.Input(
                    id='date',
                    type='date'
                )
            ],
            style={
                'font-family': 'sans-serif'
            }
        ),

        dcc.Graph(
            id='upload-status',
            figure={
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
                        text=[
                            status[x[2]]
                            for x in upload_status if x[2] == i
                        ],
                        hovertext=[
                            '{}:{} {}'.format(x[0], x[1], status[i])
                            for x in upload_status if x[2] == i
                        ],
                        mode='markers',
                        opacity=0.8,
                        marker={
                            'symbol': 'square',
                            'size': 7,
                            'line': {'width': 0.5, 'color': 'gray'},
                            'color': colors[i]
                        },
                        name=status[i]
                    ) for i in range(-1, 3, 1)
                ],
                'layout': go.Layout(
                    xaxis={
                        'title': 'Minute',
                        'tickmode': 'array',
                        'tickvals': [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
                        'color': '#7f7f7f',
                        'gridcolor': '#7f7f7f'
                    },
                    yaxis={
                        'title': 'Hour',
                        # 'zeroline': False,
                        'tickmode': 'array',
                        'tickvals': [0, 6, 12, 18],
                        'color': '#7f7f7f',
                        'gridcolor': '#7f7f7f'
                    },
                    margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
                    legend={'x': 0, 'y': 1.3},
                    hovermode='closest'
                )
            }
        )
    ])


@app.callback(
    output=Output('upload-status', 'figure'),
    inputs=[Input('date', 'value')]
)
def fun(date):
    connection = psycopg2.connect("dbname={} ".format(meta_db) +
                                  "user={} ".format(rds_db_user) +
                                  "host={} ".format(rds_host) +
                                  "password='{}'".format(password))
    cur = connection.cursor()

    upload_status = []

    for i in range(24):
        for j in range(60):
            upload_status.append([i, j, -1])

    select_latest_file_status = "SELECT max({}) AS time, {} AS file, {} AS status " \
                                    .format(time_field, file_field, status_field) \
                                + "FROM {} ".format(xml_log_table) \
                                + "GROUP BY {}, {}".format(file_field, status_field)

    query = "SELECT file, status FROM ({}) as t ".format(select_latest_file_status) \
            + "WHERE file LIKE 'Traffic/{}/%Trafficspeed%';".format(date)

    cur.execute(query)
    rows = cur.fetchall()
    connection.close()

    for row in rows:
        time = row[0].split('/')[2][:4]
        stat = row[1]
        hour, minute = int(time[:2]), int(time[2:])
        upload_status[hour * 60 + minute] = [hour, minute, stat]

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
                text=[
                    status[x[2]]
                    for x in upload_status if x[2] == i
                ],
                hovertext=[
                    '{}:{} {}'.format(x[0], x[1], status[i])
                    for x in upload_status if x[2] == i
                ],
                mode='markers',
                opacity=0.8,
                marker={
                    'symbol': 'square',
                    'size': 7,
                    'line': {'width': 0.5, 'color': 'gray'},
                    'color': colors[i]
                },
                name=status[i]
            ) for i in range(-1, 3, 1)
        ],
        'layout': go.Layout(
            xaxis={
                'title': 'Minute',
                'tickmode': 'array',
                'tickvals': [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60],
                'color': '#7f7f7f',
                'gridcolor': '#7f7f7f'
            },
            yaxis={
                'title': 'Hour',
                'tickmode': 'array',
                'tickvals': [0, 6, 12, 18, 24],
                'color': '#7f7f7f',
                'gridcolor': '#7f7f7f'
            },
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': 1.2},
            hovermode='closest'
        )
    }


if __name__ == '__main__':
    app.run_server(host='0.0.0.0')
