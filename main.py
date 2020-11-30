import boto3
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import dash_canvas
import dash_table
import dash_html_components as html
import dash_core_components as dcc

import pandas as pd
import numpy as np
import plotly.express as px

from flask_sqlalchemy import SQLAlchemy
from flask import Flask

#server = Flask(__name__)
#app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
#app.server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app = dash.Dash(__name__)
server = app.server
app.config.suppress_callback_exceptions = True
#app.server.config["SQLALCHEMY_DATABASE_URI"] = "postgres://kcfwfqwznavpjq:9473936daf43bff3d17c1dd8ab2c28144dfbf677\
#14cb30622e3017bbe55cdeac@ec2-34-197-188-147.compute-1.amazonaws.com:5432/d9eat64jon4dti"

#db = SQLAlchemy(app.server)

# -----------------------

columns_labels = ['Image File Name ', 'Class']
columns = [{'name': i, "id": i} for i in columns_labels]
columns[-1]['presentation'] = 'dropdown'

diagnosises_labels = ['Healthy', 'Mild', 'Moderate', 'Severe', 'Proliferative']
diagnosises = [{'label': i, 'value': i} for i in diagnosises_labels]

# ----------------------------------------------------------------------------------------------
s3_client = boto3.client('s3')
s3_resource = boto3.resource('s3')

bucket_name = 'eye-fundi-images'
my_bucket = s3_resource.Bucket(bucket_name)
images = []

for file in my_bucket.objects.all():
    params = {'Bucket': bucket_name, 'Key': file.key}
    url = s3_client.generate_presigned_url('get_object', params, ExpiresIn=3600)
    images.append({'Bucket': bucket_name, 'Key': file.key, 'ImgURL': url})

# ----------------------------------------------------------------------------------------------
table_content = []
current_img_index = -2

app.layout = html.Div([

    html.H1("Label the below image by pressing Label button below it and to display the next image:",
            className="display-3"),
    html.Div([
        dash_canvas.DashCanvas(
            id='canvas',
            tool='rectangle',
            lineWidth=2,
            lineColor='rgba(0, 255, 0, 0.5)',
            hide_buttons=['pencil', 'line'],
            goButtonTitle='Label',
        )
    ]),
    html.H5('Note: "Healthy" is the default labeling value, you can adjust it by clicking on the value and choose\
         from the dropdown list values.'),
    html.Div([
        dash_table.DataTable(
            id='table',
            columns=columns,
            editable=True,
            style_table={'overflowY': 'auto'},
            style_cell={'textAlign': 'left', 'minWidth': '100px', 'width': '100px', 'maxWidth': '100px'},
            dropdown={
                'Class': {
                    'options': diagnosises
                },
            },
        )
    ]),
    html.Hr(className="my-2"),
    html.Div([
        html.Button("Export Table to Excel", id='excel_btn', n_clicks=0),
        html.Button("Submit Table", id='submit_btn', n_clicks=0),
    ]),
    # for notification when saving to excel or database
    html.Div(id='placeholder', children=[]),
    dcc.Store(id="store", data=0),
    dcc.Interval(id='interval', interval=1000),

])


@app.callback(
    [Output('table', 'data'),
     Output('canvas', 'image_content')],
    [Input('canvas', 'json_data')],
    [State('table', 'data')]
)
def label_image(json_data, table_data):
    global current_img_index
    all_table_data = []

    if json_data is not None:
        if table_data is not None:
            for img in table_data:
                img_val = []
                for i in img.values():
                    img_val.append(i)
                all_table_data.append(img_val)

        current_img_index += 1
        if current_img_index > len(images) - 2:
            current_img_index = -2
            raise PreventUpdate
        else:
            if 0 <= current_img_index < len(images) - 2:
                all_table_data.append([images[current_img_index]['Key'], 'Healthy'])

    df = pd.DataFrame(all_table_data, columns=columns_labels)
    return df.to_dict('records'), images[current_img_index]['ImgURL']


@app.callback(
    [Output('placeholder', 'children'),
     Output("store", "data")],
    [Input('excel_btn', 'n_clicks'),
     Input('submit_btn', 'n_clicks'),
     Input("interval", "n_intervals")],
    [State('table', 'data'),
     State('store', 'data')]
)
def df_to_csv(excel_clicks, submit_clicks, n_intervals, table_data, sec):
    no_notification = html.Plaintext("", style={'margin': "0px"})
    notification_text = html.Plaintext("The Shown Table Data has been saved.",
                                       style={'color': 'green', 'font-weight': 'bold', 'font-size': 'large'})
    input_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    if input_triggered == "excel_btn":
        sec = 10
        df = pd.DataFrame(table_data)
        df.to_csv("Labeled_Eye_Images.csv")
        return notification_text, sec
    elif input_triggered == 'submit_btn':
        sec = 10
        return notification_text, sec
    elif input_triggered == 'interval' and sec > 0:
        sec -= 1
        if sec > 0:
            return notification_text, sec
        else:
            return no_notification, sec
    elif sec == 0:
        return no_notification, sec

#@app.callback(Output('table', 'data'),
#              [Input('submit_btn', 'n_clicks')])
#def populate_datatable(n_clicks):
#    df = pd.read_sql_table('productlist', con=db.engine)
#    return df.to_dict('records')



if __name__ == '__main__':
    app.run_server(debug=True)