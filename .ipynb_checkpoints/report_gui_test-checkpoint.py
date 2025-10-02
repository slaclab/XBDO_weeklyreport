from ipywidgets import FloatText, HTML
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import requests, io, pytz

import ipywidgets as widgets
from ipywidgets import VBox, HBox, Button, Text, Dropdown, IntText, Output, Select, DatePicker

# --- EPICS PVs ---
epics_pvs = {
    "GMD": ("GDET:FEE1:362:ENRC", "#00008B"),        # deep blue
    "XGMD": ("EM2K0:XGMD:HPS:milliJoulesPerPulse", "#8B0000"),  # dark red
}

# --- Hutch color mapping ---
hutch_colors = {
    "XCS": "purple",
    "CXI": "red",
    "MFX": "orange",
    "MEC": "yellow",
    "TXI": "magenta",
    "XPP": "brown",
    "RIX": "#B99A7B",
    "TMO": "blue",
    "MD" : "gray",
}

# --- Hutch ICS URLs ---
hutch_calendars = {
    "TMO": "https://www.google.com/calendar/ical/tauubmn9n6evkir835i4uqde3c%40group.calendar.google.com/public/basic.ics",
    "TXI": "https://www.google.com/calendar/ical/ag90tn65tk169kgpkt8i7286ns%40group.calendar.google.com/public/basic.ics",
    "XPP": "https://www.google.com/calendar/ical/6sr414nehbugn2k67efq71mppg%40group.calendar.google.com/public/basic.ics",
    "RIX": "https://calendar.google.com/calendar/ical/rf402b8ts02ultfjc62l8clalk%40group.calendar.google.com/public/basic.ics",
    "XCS": "https://www.google.com/calendar/ical/ljjr3de15ianjh42ahlqvcv5s4%40group.calendar.google.com/public/basic.ics",
    "MFX": "https://www.google.com/calendar/ical/lun28fjakluvivt5q4fj6qu2eg%40group.calendar.google.com/public/basic.ics",
    "CXI": "https://www.google.com/calendar/ical/lt8askfj7kivnsfki1dgc63ifs%40group.calendar.google.com/public/basic.ics",
    "MEC": "https://www.google.com/calendar/ical/nka5r8ffmrik5jcdih8nu73r1k%40group.calendar.google.com/public/basic.ics"
}

# --- ICS Parsing ---
def parse_dt(dt_str):
    if dt_str.endswith("Z"):
        return datetime.strptime(dt_str, "%Y%m%dT%H%M%SZ")
    elif "T" in dt_str:
        return datetime.strptime(dt_str, "%Y%m%dT%H%M%S")
    else:
        return datetime.strptime(dt_str, "%Y%m%d")

def load_hutch_patches(hutch_name, url, start_dt=None, end_dt=None, tz="America/Los_Angeles"):
    r = requests.get(url)
    r.raise_for_status()
    lines = r.text.splitlines()
    
    patches = []
    inside_event, event = False, {}
    
    for line in lines:
        if line.startswith("BEGIN:VEVENT"):
            inside_event, event = True, {}
        elif line.startswith("END:VEVENT"):
            inside_event = False
            if "DTSTART" in event and "DTEND" in event:
                start = parse_dt(event["DTSTART"])
                end   = parse_dt(event["DTEND"])
                start = pytz.UTC.localize(start).astimezone(pytz.timezone(tz)) if start.tzinfo is None else start
                end   = pytz.UTC.localize(end).astimezone(pytz.timezone(tz)) if end.tzinfo is None else end
                if start_dt and end_dt:
                    if end < start_dt or start > end_dt:
                        continue
                minutes = int((end - start).total_seconds() / 60)
                patches.append((start.strftime("%Y-%m-%d %H:%M"), minutes, hutch_name))
        elif inside_event:
            if line.startswith("DTSTART"):
                event["DTSTART"] = line.split(":", 1)[1]
            elif line.startswith("DTEND"):
                event["DTEND"] = line.split(":", 1)[1]
    return patches

# --- PV Data Fetch ---
def fetch_pv_data_as_df(pv: str, start: str, end: str):
    url = f"https://pswww.slac.stanford.edu/archiveviewer/retrieval/data/getData.csv?pv={pv}&from={start}&to={end}"
    r = requests.get(url)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), header=None,
                     names=["Timestamp", "Value1", "Value2", "Value3", "Value4"])
    df = df[pd.to_numeric(df["Timestamp"], errors='coerce').notnull()]
    df["Timestamp"] = pd.to_datetime(df["Timestamp"].astype(float), unit='s')
    df["Timestamp"] = df["Timestamp"].dt.tz_localize("UTC").dt.tz_convert("America/Los_Angeles")
    df["Value1"] = pd.to_numeric(df["Value1"], errors='coerce')
    return df

# --- Report Plot ---
def report_range(end_date: str, period: str, hutch_patches=[], comment_patches=[], threshold=None):
    tz = pytz.timezone("America/Los_Angeles")
    try:
        end_dt = datetime.s_
