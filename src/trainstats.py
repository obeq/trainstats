from datetime import timedelta
import streamlit as st

import requests
import pandas as pd

from dotenv import load_dotenv
load_dotenv()

import os

from xml.dom.minidom import Document, Element

TRAFIKVERKET_API=os.getenv("TRAFIKVERKET_KEY")
TRAFIKVERKET_URL="https://api.trafikinfo.trafikverket.se/v2/data.json"

def create_question(object_type: str, filters: list, includes: list, namespace: str | None = None, schemaversion: str = "1,9", limit: int = 1000) -> str:
    """Create a question for the Trafikverket API."""

    if TRAFIKVERKET_API is None:
        raise ValueError("API key not found")

    root = Document()

    request = root.createElement("REQUEST")
    root.appendChild(request)

    login = root.createElement("LOGIN")
    login.setAttribute("authenticationkey", TRAFIKVERKET_API)
    request.appendChild(login)

    query = root.createElement("QUERY")
    query.setAttribute("objecttype", object_type)
    query.setAttribute("schemaversion", schemaversion)
    query.setAttribute("limit", str(limit))
    if namespace is not None:
        query.setAttribute("namespace", namespace)
    request.appendChild(query)

    filter = root.createElement("FILTER")
    query.appendChild(filter)

    def get_filter(f: dict) -> Element:
        elem = root.createElement(f['type'])
        if 'children' in f:
            for child in f['children']:
                elem.appendChild(get_filter(child))
        for key, value in f.items():
            if key not in ['type', 'children']:
                elem.setAttribute(key, value)
        return elem

    for f in filters:
        elem = get_filter(f)
        filter.appendChild(elem)

    for i in includes:
        elem = root.createElement("INCLUDE")
        elem.appendChild(root.createTextNode(i))
        query.appendChild(elem)

    return root.toprettyxml()

@st.cache_data(ttl=timedelta(minutes=1))
def get_data(question: str) -> dict:
    """Get data from Trafikverket API."""

    headers = {
        "Content-Type": "text/xml"
    }
    resp = requests.post(TRAFIKVERKET_URL, data=question, headers=headers)

    return resp.json()['RESPONSE']['RESULT'][0]

@st.cache_data
def get_signature(search_text: str = "") -> pd.DataFrame:
    """Get the signatures for a location."""

    question = create_question(
        object_type="TrainStation",
        filters=[],
        includes=["LocationSignature", "AdvertisedLocationName"],
        namespace="rail.infrastructure",
        schemaversion="1.5",
        limit=5000
    )

    all_locations = get_data(
        question
    )

    df_locations = pd.DataFrame(all_locations['TrainStation'])

    if not search_text:
        return df_locations

    # df_locations['AdvertisedLocationName'] = df_locations['AdvertisedLocationName'].str.lower()

    return df_locations[df_locations['AdvertisedLocationName'].str.find(search_text) > -1]

@st.cache_data(ttl=timedelta(minutes=1))
def get_data_for_station(locations: list[str]) -> pd.DataFrame | None:
    """Get data for a specific station."""

    filters = [
        {
            "type": "GT",
            "name": "AdvertisedTimeAtLocation",
            "value": "$dateadd(-1)"
        },
        {
            "type": "LT",
            "name": "AdvertisedTimeAtLocation",
            "value": "$now"
        }
    ]
    or_filters = {
        "type": "OR",
        "children": []
    }
    for location in locations:
        or_filters['children'].append(
            {
                "type": "EQ",
                "name": "LocationSignature",
                "value": location
            }
        )
    filters.append(or_filters)

    question = create_question(
        object_type="TrainAnnouncement",
        filters=filters,
        includes=[],
        schemaversion="1.9",
        limit=1000
    )

    print(question)

    traininfo = get_data(question)

    if 'TrainAnnouncement' not in traininfo:
        return None

    df = pd.DataFrame(traininfo["TrainAnnouncement"])

    df = df[['AdvertisedTimeAtLocation', 'TimeAtLocation', 'ActivityType']]

    df['AdvertisedTimeAtLocation'] = pd.to_datetime(df['AdvertisedTimeAtLocation'])
    df['TimeAtLocation'] = pd.to_datetime(df['TimeAtLocation'])

    df.loc[:, 'Delay'] = (df['TimeAtLocation'] - df['AdvertisedTimeAtLocation']).dt.total_seconds() / 60

    return df


locations = get_signature()
location_names = st.multiselect("Select the station", locations['AdvertisedLocationName'])
locations = locations[locations['AdvertisedLocationName'].isin(location_names)]['LocationSignature'].values

include_departures = st.checkbox("Departures", value=True)
include_arrivals = st.checkbox("Arrivals", value=True)
activities = []
if include_departures:
    activities.append("Avgang")
if include_arrivals:
    activities.append("Ankomst")

if locations is not []:
    df = get_data_for_station(list(locations))

    if df is None:
        st.write("No data found")
        st.stop()

    df = df[df['ActivityType'].isin(activities)]

    # st.line_chart(df, x='AdvertisedTimeAtLocation', y='Delay', height=880)
    st.scatter_chart(df, x='AdvertisedTimeAtLocation', y='Delay', height=660, color='ActivityType')