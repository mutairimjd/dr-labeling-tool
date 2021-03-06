import boto3
import dash
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash_extensions import Download
from dash_extensions.snippets import send_data_frame
import dash_canvas
import dash_table
import dash_html_components as html
import dash_core_components as dcc
from os import getenv
import pandas as pd

from flask_sqlalchemy import SQLAlchemy
from flask import Flask

server = Flask(__name__)
app = dash.Dash(__name__, server=server, suppress_callback_exceptions=True)
app.server.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.server.config["SQLALCHEMY_DATABASE_URI"] = "postgres://sijsukdyexzkgd:d3eb93de50667df727a076329de19ad474eca375fe2cd\
634209dc4911dfb91b4@ec2-54-163-47-62.compute-1.amazonaws.com:5432/dbi07hebtnf8ic"

db = SQLAlchemy(app.server)


class Results(db.Model):
    __tablename__ = 'labeling-results'

    Image_name = db.Column('Image File Name', db.String(40), nullable=False, primary_key=True)
    Class_name = db.Column('Class', db.String(40), nullable=False)

    def __init__(self, image_name, class_name):
        self.Image_name = image_name
        self.Class_name = class_name


# -----------------------

columns_labels = ['Image File Name', 'Class']

columns = [{'name': i, "id": i} for i in columns_labels]
columns[-1]['presentation'] = 'dropdown'

diagnosises_labels = ['Healthy', 'Mild', 'Moderate', 'Severe', 'Proliferative']
diagnosises = [{'label': i, 'value': i} for i in diagnosises_labels]

# ----------------------------------------------------------------------------------------------
boto_kwargs = {
    "aws_access_key_id": getenv("AWS_ACCESS_KEY_ID"),
    "aws_secret_access_key": getenv("AWS_SECRET_ACCESS_KEY"),
    "region_name": getenv("AWS_REGION"),
}
s3_client = boto3.Session(**boto_kwargs).client("s3")
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
        # for notification when saving to excel
        html.Div(id='excel_notification_placeholder', children=[]),
        dcc.Store(id="excel_notification_store", data=0),
        dcc.Interval(id='excel_notification_nterval', interval=1000),
        Download(id="download"),
        # for notification when saving to database
        html.Div(id='db_notification_placeholder', children=[]),
        dcc.Store(id="db_notification_store", data=0),
        dcc.Interval(id='db_notification_interval', interval=1000),

    ]),
])


@app.callback(
    [Output('table', 'data'),
     Output('canvas', 'image_content')],
    [Input('canvas', 'json_data')],
    [State('table', 'data')]
)
def label_image(json_data, table_data):
    global current_img_index
    if json_data is not None:
        current_img_index += 1
        if current_img_index > len(images) - 2:
            current_img_index = -2
            raise PreventUpdate
        else:
            if 0 <= current_img_index < len(images) - 2:
                table_data.append({'Image File Name': images[current_img_index]['Key'], 'Class': 'Healthy'})
    df = pd.DataFrame(table_data)
    return df.to_dict('records'), images[current_img_index]['ImgURL']


@app.callback(
    [Output("download", "data"),
     Output('excel_notification_placeholder', 'children'),
     Output("excel_notification_store", "data")],
    [Input('excel_btn', 'n_clicks'),
     Input("excel_notification_nterval", "n_intervals")],
    [State('table', 'data'),
     State('excel_notification_store', 'data')]
)
def save_to_csv(n_clicks, n_intervals, table_data, sec):
    no_notification = html.Plaintext("", style={'margin': "0px"})
    notification_text = html.Plaintext("The Shown Table Data has been saved to the excel sheet.",
                                       style={'color': 'green', 'font-weight': 'bold', 'font-size': 'large'})
    input_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]
    if input_triggered == "excel_btn" and n_clicks:
        sec = 10
        df = pd.DataFrame(table_data)
        return send_data_frame(df.to_csv, filename="Labeled_Eye_Images.csv"), notification_text, sec
    elif input_triggered == 'excel_notification_nterval' and sec > 0:
        sec = sec - 1
        if sec > 0:
            return None, notification_text, sec
        else:
            return None, no_notification, sec
    elif sec == 0:
        return None, no_notification, sec

@app.callback(
    [Output('db_notification_placeholder', 'children'),
     Output("db_notification_store", "data")],
    [Input('submit_btn', 'n_clicks'),
     Input("db_notification_interval", "n_intervals")],
    [State('table', 'data'),
     State('db_notification_store', 'data')]
)
def save_to_db(n_clicks, n_intervals, table_data, sec):
    no_notification = html.Plaintext("", style={'margin': "0px"})
    notification_text = html.Plaintext("The Shown Table Data has been saved to the database.",
                                       style={'color': 'green', 'font-weight': 'bold', 'font-size': 'large'})
    input_triggered = dash.callback_context.triggered[0]["prop_id"].split(".")[0]

    if input_triggered == 'submit_btn':
        sec = 10
        df = pd.DataFrame(table_data)
        df.to_sql('labeling-results', con=db.engine, if_exists='replace', index_label=False)
        return notification_text, sec
    elif input_triggered == 'db_notification_interval' and sec > 0:
        sec = sec - 1
        if sec > 0:
            return notification_text, sec
        else:
            return no_notification, sec
    elif sec == 0:
        return no_notification, sec


if __name__ == '__main__':
    app.run_server(debug=True)
