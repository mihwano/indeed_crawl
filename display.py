from pymongo import MongoClient
import time
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
import pdb, sys
import webbrowser
import os
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objs as go
from plotly import tools
from dash.dependencies import Input, Output, State
import simplejson
import easygui as eg

access_token="pk.eyJ1IjoibWlod2FubyIsImEiOiJjajhmMG5oM3YxYTI5MndybHNlODAxZW5pIn0.1U54aBjp-U-NlkzUFoktTQ"

client = MongoClient()
db = client["jobs_db"]
collection = db['indeed_jobs']

styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll',
        'padding-top':5}
    }

def resolve_locations(df):
    unique_loc = {}
    for i in range(len(df)):
        if (df["lat"].iloc[i], df["lon"].iloc[i]) not in unique_loc:
            unique_loc[(df["lat"].iloc[i], df["lon"].iloc[i])] = 1
        else:
            unique_loc[(df["lat"].iloc[i], df["lon"].iloc[i])] += 1
    for i in range(len(df)):
        if unique_loc[(df["lat"].iloc[i], df["lon"].iloc[i])] > 1:
            df.loc[i, "lat"] = df.loc[i, "lat"] + np.random.uniform(-0.005, 0.005)
            df.loc[i, "lon"] = df.loc[i, "lon"] + np.random.uniform(-0.005, 0.005)
    return df


def retrieve_postings(**kargs):
    try:
        data = collection.find(kwargs)
    except:
        data = collection.find()
    df = pd.DataFrame(list(data))
    df = resolve_locations(df)
    return df


def base_map():
    return dict(accesstoken=access_token, bearing=0, pitch=0, style='light',
                zoom=9, center=dict(lat=38.88,lon=-77.10))


def experience_req(df):
    experience = []
    for item in [x.lower() for x in df["job_title"].values]:
        if any(char in item for char in ["jr.", "jr", "junior", "entry-level", "entry level"]):
            experience.append("junior")
        elif any(char in item for char in ["sr.", "sr", "senior"]):
            experience.append("senior")
        elif any(char in item for char in ["manager"]):
            experience.append("manager")
        elif any(char in item for char in ["dir.", "director"]):
            experience.append("director")
        else:
            experience.append("journeyman")
    df["experience"] = experience
    return df


def colors(df):
    df["colors"] = "green"
    for i in range(len(df)):
        if df["seen-interested"].iloc[i] == True:
            df["colors"].iloc[i] = "yellow"
            continue
        if df["seen_uninterested"].iloc[i] == True:
            df["colors"].iloc[i] = "blue"
            continue
        if df["applied_to"].iloc[i] == True:
            df["colors"].iloc[i] = "red"
            continue
    return df


def applications_counts(col):
    application = df.groupby(["timestamp", col], as_index=False)["job_title"].count()
    application = application[application[col]==True].rename(columns={"job_title":"count"})
    application = pd.merge(df, application, how="left", on=["timestamp", col])
    application = application.sort_values("timestamp")
    application["count"] = application["count"].fillna(0)
    apps_count = []
    count = 0
    for item in application["count"]:
        count += item
        apps_count.append(count)
    return application, apps_count


app = dash.Dash()

df = retrieve_postings()
df = experience_req(df)
df = colors(df)
df['timestamp'] = pd.to_datetime(df['timestamp'], format='%m/%d/%y')
current_date = datetime.strptime(time.strftime("%x"), '%m/%d/%y')

app.css.append_css({
    'external_url': 'https://codepen.io/chriddyp/pen/bWLwgP.css'})

def make_subplot():
    barchart = df.groupby("experience", as_index=False)["job_title"].count()
    application, apps_count = applications_counts("applied_to")
    replies, reply_count = applications_counts("reply_sent")

    trace1 = go.Bar(
        x=barchart["experience"],
        y=barchart["job_title"],
        showlegend=False)
    trace2 = go.Bar(
        x=application["timestamp"],
        y=[x for x in application["count"]],
        name="daily nbr of resume sent")
    trace3 = go.Scatter(
        x=application["timestamp"],
        y=apps_count,
        mode='lines',
        name="sent resume count")
    trace4 = go.Scatter(
        x=application["timestamp"],
        y=reply_count,
        mode='lines',
        name="replies count")

    fig = tools.make_subplots(rows=2, cols=1,
                              subplot_titles=('barchart','applications'))
    fig.append_trace(trace1, 1, 1)
    fig.append_trace(trace2, 2, 1)
    fig.append_trace(trace3, 2, 1)
    fig.append_trace(trace4, 2, 1)
    fig['layout'].update(height=700, width=500)
    return fig


app.layout = html.Div(style={'height': 30},
                      children=[
                                html.H5(children='Job Postings NoVa area',
                                        style={'textAlign': 'center', 'color': 'black', 'font':'bold'}),
    html.Div([
        html.Div([
                dcc.Graph(id='charts',
                          figure=make_subplot()),
                ], style={'height': 800}, className="four columns"),
    
        html.Div([
            dcc.Dropdown(
                id="experience-level",
                options=[
                    {'label': 'Entry-level Jobs', 'value': 'junior'},
                    {'label': 'Journeyman Jobs', 'value': 'journeyman'},
                    {'label': 'Senior Jobs', 'value': 'senior'},
                    {'label': 'Manager Jobs', 'value': 'manager'},
                    {'label': 'Director Jobs', 'value': 'director'}
                ],
                multi=True,
                value=['junior', 'journeyman', 'senior', 'manager', 'director']
            ),
            dcc.Dropdown(
                id="posted_date",
                options=[
                    {'label': "All postings", 'value': current_date-timedelta(days=365)},
                    {'label': "Last day", 'value': current_date-timedelta(days=1)},
                    {'label': "Last 3 days", 'value': current_date-timedelta(days=3)},
                    {'label': "Last week", 'value': current_date-timedelta(days=7)},
                    {'label': "Last 2 weeks", 'value': current_date-timedelta(days=14)}],
                value="All postings"),
            dcc.Graph(id='mapbox', animate=True,
                      figure={'data': [go.Scattermapbox(
                                        lat=df["lat"].values,
                                        lon=df["lon"].values,
                                        mode='markers',
                                        marker={'size':10, 'color':df["colors"].values},
                                        text = ['<a href="%s"><b>%s</b></a><br>%s' \
                                                %x for x in zip(df['url_link'], df['job_title'], \
                                                                df["company"])],
                                        hoverinfo="text",
                                        )],
                              'layout': go.Layout(autosize=True,
                                                  hoverlabel={'bgcolor': 'white', 'font': {'size':16, 'color': 'black'}},
                                                  height=650,
                                                  width=900,
                                                  hovermode='closest',
                                                  margin={'l': 50, 'b': 10, 't': 10, 'r': 80},
                                                  mapbox=base_map())
                      },
                    ),
            html.Pre(id='click-data', style={'opacity':0.01}),
                ], className="six columns"),
        ], className="row")
    ])

@app.callback(
    Output('mapbox', 'figure'),
          [Input('experience-level', 'value'),
          Input('posted_date', 'value')])
def update_mapbox_exp(selected_experience, selected_date):
    filtered_df = df[(df['experience'].isin(selected_experience)) & \
                     (df['timestamp']>=selected_date)]
    return {'data': [go.Scattermapbox(
                    lat=filtered_df["lat"].values,
                    lon=filtered_df["lon"].values,
                    mode='markers',
                    marker={'size':10, 'color':filtered_df["colors"].values},
                    text = ['<a href="%s"><b>%s</b></a><br>%s' \
                            %x for x in zip(filtered_df['url_link'], filtered_df['job_title'], \
                            filtered_df["company"])],
                    hoverinfo="text",
                    )],
            'layout': go.Layout(autosize=True,
                                hoverlabel={'bgcolor': 'white', 'font': {'size':16, 'color': 'black'}},
                                height=650,
                                width=900,
                                hovermode='closest',
                                margin={'l': 50, 'b': 30, 't': 30, 'r': 80},
                                mapbox=base_map())}


@app.callback(
    Output('click-data', 'children'),
    [Input('mapbox', 'clickData')])
def display_click_data(clickData):
    res = eg.buttonbox('Click on your choice','Action regarding this posting',
                      ('Mark as seen - interesting', 'Mark as seen - throw out', 'Leave it for now', 'Mark as applied to'))
    company = clickData["points"][0]["text"].split("<br>")[-1]
    job_title = clickData["points"][0]["text"].split("<b>")[1].split("</b>")[0]
    url_link = clickData["points"][0]["text"].split("href=")[1].split("><b>")[0]
    url_link = url_link.replace('"','')
    if res == 'Mark as seen - interesting':
        collection.update_one({'company': company, 'job_title': job_title,
                               'url_link': url_link}, {'$set': {'seen-intereted':True}})
    elif res == 'Mark as seen - throw out':
        collection.update_one({'company': company, 'job_title': job_title,
                                'url_link': url_link}, {'$set': {'seen_uninterested':True, 'seen-interested':False}})
    elif res == 'Mark as applied to':
        collection.update_one({'company': company, 'job_title': job_title,
                                'url_link': url_link}, {'$set': {'applied_to':True}})
    return


#webbrowser.open("http://127.0.0.1:8050/")
if __name__ == '__main__':  
    app.run_server(debug=True)
