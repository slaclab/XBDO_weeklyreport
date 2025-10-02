import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import requests, io, pytz
import re

import ipywidgets as widgets
from ipywidgets import VBox, HBox, Button, Text, Dropdown, IntText, Output, Select, DatePicker

# EPICS PVs
epics_pvs = {
    "GMD": ("GDET:FEE1:362:ENRC", "#00008B"),        # deep blue
    "XGMD": ("EM2K0:XGMD:HPS:milliJoulesPerPulse", "#8B0000"),  # dark red
}

# Hutch color mapping
hutch_colors = {
    "XCS": "purple",
    "CXI": "red",
    "MFX": "orange",
    "MEC": "yellow",
    "TXI": "magenta",
    "TMO": "blue",
    "RIX": "#B99A7B",
    "chemRIX": "#E8C19A",
    "MD" : "gray",
    "MD-SC" : "gray",
    "Other" : "gray",
}

# CXI - #EF2F2F
# MFX - #F7C707
# MEC - #F4F811
# XPP - #165806
# TMO - #0737F7
# TXI - #BE29EC
# XCS - #8430C8
# with the added bonus of RIX - #B99A7B #E8C19A

hutch_calendars = {
    "TMO": "https://calendar.google.com/calendar/ical/e8c51288aa6fe89c7304f665e4ff54240059b52c0f2241d0dbde91399f562f33%40group.calendar.google.com/public/basic.ics",
    "TXI": "https://www.google.com/calendar/ical/ag90tn65tk169kgpkt8i7286ns%40group.calendar.google.com/public/basic.ics",
    "RIX": "https://calendar.google.com/calendar/ical/a926446f7df37ebc0ff9ddc4cf09abd2fa696c53769f43580aea78ae97a19912%40group.calendar.google.com/public/basic.ics",
    "chemRIX": "https://calendar.google.com/calendar/ical/0e4eed830248da6cfb26ee3c734bdbfa4b482647bc828992547c4c8f5de51d46%40group.calendar.google.com/public/basic.ics",
    "XPP": "https://calendar.google.com/calendar/ical/6sr414nehbugn2k67efq71mppg%40group.calendar.google.com/public/basic.ics",
    "XCS": "https://calendar.google.com/calendar/ical/ljjr3de15ianjh42ahlqvcv5s4%40group.calendar.google.com/public/basic.ics",
    "CXI": "https://calendar.google.com/calendar/ical/lt8askfj7kivnsfki1dgc63ifs%40group.calendar.google.com/public/basic.ics",
    "MEC": "https://calendar.google.com/calendar/ical/nka5r8ffmrik5jcdih8nu73r1k%40group.calendar.google.com/public/basic.ics",
    "MFX": "https://calendar.google.com/calendar/ical/lun28fjakluvivt5q4fj6qu2eg%40group.calendar.google.com/public/basic.ics",
    "MD": "https://calendar.google.com/calendar/ical/4edfcc9b959034909ac9035917482370c007b28dceacb6edd9c9223f0f944a6e%40group.calendar.google.com/public/basic.ics",
}

#    "MD-SC": "https://calendar.google.com/calendar/ical/4edfcc9b959034909ac9035917482370c007b28dceacb6edd9c9223f0f944a6e%40group.calendar.google.com/public/basic.ics",
#"MD-SC_FEEH" : "https://calendar.google.com/calendar/ical/266ac5957019dc9018cb2a27462d97029787edde0a0c3c7f4bb9d1434fa6b417%40group.calendar.google.com/public/basic.ics"

    # "XPP": "https://www.google.com/calendar/ical/6sr414nehbugn2k67efq71mppg%40group.calendar.google.com/public/basic.ics",
    # "XCS": "https://www.google.com/calendar/ical/ljjr3de15ianjh42ahlqvcv5s4%40group.calendar.google.com/public/basic.ics",
    # "MFX": "https://www.google.com/calendar/ical/lun28fjakluvivt5q4fj6qu2eg%40group.calendar.google.com/public/basic.ics",
    # "CXI": "https://www.google.com/calendar/ical/lt8askfj7kivnsfki1dgc63ifs%40group.calendar.google.com/public/basic.ics",
    # "MEC": "https://www.google.com/calendar/ical/nka5r8ffmrik5jcdih8nu73r1k%40group.calendar.google.com/public/basic.ics",


def sync_hutch_from_calendar_noics( end_date_str, period_str, hutch_patches):
    tz = pytz.timezone("America/Los_Angeles")
    
    try:
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d %H:%M")
    end_dt = tz.localize(end_dt)
    
    if period_str.endswith('d'):
        delta = timedelta(days=int(period_str[:-1]))
    elif period_str.endswith('h'):
        delta = timedelta(hours=int(period_str[:-1]))
    else:
        raise ValueError("period is 'Nd' or 'Nh.")
    start_dt = end_dt - delta
    total_added = 0

    for hutch_name, url in hutch_calendars.items():
        r = requests.get(url)
        r.raise_for_status()
        text = r.text

        events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, flags=re.DOTALL)
        for ev in events:
            dtstart_match = re.search(r"DTSTART(?:;[^:]*)?:(\d{8}T\d{6}Z)", ev)
            dtend_match   = re.search(r"DTEND(?:;[^:]*)?:(\d{8}T\d{6}Z)", ev)
            if not dtstart_match or not dtend_match:
                continue
            
            ev_start = datetime.strptime(dtstart_match.group(1), "%Y%m%dT%H%M%SZ")
            ev_end   = datetime.strptime(dtend_match.group(1), "%Y%m%dT%H%M%SZ")
            ev_start = pytz.utc.localize(ev_start).astimezone(tz)
            ev_end   = pytz.utc.localize(ev_end).astimezone(tz)
            
            if ev_end >= start_dt and ev_start <= end_dt:
                minutes = int((ev_end - ev_start).total_seconds() / 60)
                hutch_patches.append((ev_start.strftime("%Y-%m-%d %H:%M"), minutes, hutch_name))
                total_added += 1
                
    return total_added

def fetch_pv_data_as_df(pv: str, start: str, end: str):
    url = f"https://pswww.slac.stanford.edu/archiveviewer/retrieval/data/getData.csv?pv={pv}&from={start}&to={end}"
    r = requests.get(url)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text), header=None,
                     names=["Timestamp", "Value1", "Value2", "Value3", "Value4"])

    df = df[pd.to_numeric(df["Timestamp"], errors='coerce').notnull()]
    df["Timestamp"] = pd.to_datetime(df["Timestamp"].astype(float), unit='s', utc=True)
    df["Timestamp"] = df["Timestamp"].dt.tz_convert("America/Los_Angeles")
    
    # Value 변환 + 시간 정렬
    df["Value1"] = pd.to_numeric(df["Value1"], errors='coerce')
    df = df.sort_values("Timestamp").reset_index(drop=True)
    
    return df

# --- Report plot ---
def report_range(end_date: str, period: str, hutch_patches=[], comment_patches=[]):
    tz = pytz.timezone("America/Los_Angeles")
    try:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d %H:%M")
    end_dt = tz.localize(end_dt)

    if period.endswith('d'):
        delta = timedelta(days=int(period[:-1]))
    elif period.endswith('h'):
        delta = timedelta(hours=int(period[:-1]))
    else:
        raise ValueError("period is 'Nd' or 'Nh.")
    start_dt = end_dt - delta

    start_time = start_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end_time   = end_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # gmd_df = fetch_pv_data_as_df(epics_pvs["GMD"][0], start_time, end_time).iloc[::10]
    # xgmd_df = fetch_pv_data_as_df(epics_pvs["XGMD"][0], start_time, end_time).iloc[::10]
    gmd_df = fetch_pv_data_as_df(epics_pvs["GMD"][0], start_time, end_time)
    xgmd_df = fetch_pv_data_as_df(epics_pvs["XGMD"][0], start_time, end_time)
    
    if len(gmd_df) > 0:
        gmd_df = gmd_df.iloc[::10]
    if len(xgmd_df) > 0:
        xgmd_df = xgmd_df.iloc[::10]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,12), sharex=False)

    # GMD
    ax1.plot(gmd_df["Timestamp"], gmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["GMD"][1], label="GMD")
    ax1.set_ylabel("HXR Pulse Energy(mJ)")
    ax1.set_title(f"Report {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
    ax1.grid(True)
    ax1.set_ylim([-0.4, 3])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M', tz=tz))
    
    # XGMD
    ax2.plot(xgmd_df["Timestamp"], xgmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["XGMD"][1], label="XGMD")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("SXR Pulse Energy(mJ)")
    ax2.grid(True)
    ax2.set_ylim([-0.4, 1.5])
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d\n%H:%M', tz=tz))
    margin = (end_dt - start_dt) * 0.05 
    ax1.set_xlim(start_dt-margin, end_dt+margin)
    ax2.set_xlim(ax1.get_xlim())
    # fig.autofmt_xdate()

    patch_ymin, patch_ymax = -0.4, -0.2
    comment_patch_ymin, comment_patch_ymax = 0, 3
    table_data = []

    for ax in [ax1, ax2]:
        for start_str, minutes, hutch in hutch_patches:
            start_patch = tz.localize(datetime.strptime(start_str, "%Y-%m-%d %H:%M"))
            end_patch = start_patch + timedelta(minutes=minutes)
            if start_dt <= end_patch and end_dt >= start_patch:
                color = hutch_colors.get(hutch, 'gray')
                if hutch in ["XCS", "CXI", "XPP", "MEC", "MFX"]:
                    target_ax = ax1
                else:
                    target_ax = ax2
                if ax is target_ax:
                    target_ax.fill_betweenx([patch_ymin, patch_ymax], start_patch, end_patch, color=color, alpha=0.8)
                    target_ax.text(start_patch + (end_patch - start_patch)/2,
                                   patch_ymin + 0.4*(patch_ymax - patch_ymin),
                                   hutch, ha='center', va='center', fontsize=8)

        sorted_comments = sorted(comment_patches,
            key=lambda x: tz.localize(datetime.strptime(x[0], "%Y-%m-%d %H:%M")))
        for i, (start_str, minutes, issue, hutch) in enumerate(sorted_comments, start=1):
            start_comment = tz.localize(datetime.strptime(start_str, "%Y-%m-%d %H:%M"))
            end_comment = start_comment + timedelta(minutes=minutes)
            if start_dt <= end_comment and end_dt >= start_comment:
                ax.fill_betweenx([comment_patch_ymin, comment_patch_ymax],
                                 start_comment, end_comment,
                                 color='gray', alpha=0.2)
                ax.text(start_comment + (end_comment - start_comment)/2,
                        comment_patch_ymin + 0.7*(comment_patch_ymax - comment_patch_ymin),
                        str(i), ha='center', va='center', fontsize=8)
                if ax is ax2: 
                    table_data.append([i, start_str, minutes, issue, hutch])

    if table_data:
        table = ax2.table(cellText=table_data,
                         colLabels=["#", "Start", "Minutes", "Issue", "Area"],
                         cellLoc='center', colLoc='center',
                         loc='bottom', bbox=[0, -0.55, 1, 0.35])  #
        table.auto_set_font_size(False)
        table.set_fontsize(8)

    plt.subplots_adjust(hspace=0.3, bottom=0.5)  
    plt.show()

# --- GUI ---
def report_gui():
    # --- report End date/time ---
    end_date_picker = DatePicker(value=datetime.today().date(), description="End date")
    end_time_text = Text(value="23:59:00", description="Time")
    period = Dropdown(options=["1d","2d","3d","4d","5d","6d","7d","8d","9d","10d","12d","14d","20d","30d"], value="7d", description="Period")
    sync_hutch_btn = Button(description="Sync Program List", button_style="info")

    # Hutch patch inputs
    now_str = datetime.today().strftime("%Y-%m-%d %H:%M")
    hutch_date = Text(value=now_str, description="Program")
    hutch_minutes = IntText(value=720, description="Minutes")
    hutch_name = Dropdown(options=list(hutch_colors.keys()), value="XCS", description="Hutch")
    add_hutch_btn = Button(description="Add Hutch", button_style="success")
    remove_hutch_btn = Button(description="Remove", button_style="danger")
    update_hutch_btn = Button(description="Update", button_style="warning")
    program_list = Select(options=[], rows=6, description="Program List", layout=widgets.Layout(width="600px"))

    # Comment inputs
    comment_date = Text(value=now_str, description="Comment")
    comment_minutes = IntText(value=60, description="Minutes")
    comment_issue = Text(value="Input short description", description="Issue")
    comment_hutch = Dropdown(options=list(hutch_colors.keys()), value="Other", description="Hutch")
    add_comment_btn = Button(description="Add Comment", button_style="info")
    remove_comment_btn = Button(description="Remove", button_style="danger")
    comment_list = Select(options=[], rows=4, description="Comments", layout=widgets.Layout(width="600px"))

    out_plot = widgets.Output()
    hutch_patches = []
    comment_patches = []

    # --- Callbacks ---
    def refresh_program_list():
        program_list.options = [f"{i+1}. {d}, {m} min, {h}" for i,(d,m,h) in enumerate(hutch_patches)]

    def add_hutch(_):
        hutch_patches.append((hutch_date.value, hutch_minutes.value, hutch_name.value))
        refresh_program_list()

    def remove_hutch(_):
        if program_list.index is not None and program_list.index >= 0:
            del hutch_patches[program_list.index]
            refresh_program_list()

    def update_hutch(_):
        if program_list.value:  
            idx = program_list.options.index(program_list.value)
            hutch_patches[idx] = (hutch_date.value, hutch_minutes.value, hutch_name.value)
            refresh_program_list()
    
    def on_hutch_select(change):
        if change["new"]:
            idx = program_list.options.index(change["new"])
            date, minutes, hutch = hutch_patches[idx]
            hutch_date.value = date
            hutch_minutes.value = minutes
            hutch_name.value = hutch

    program_list.observe(on_hutch_select, names="value")

    def add_comment(_):
        comment_patches.append((comment_date.value, comment_minutes.value, comment_issue.value, comment_hutch.value))
        comment_list.options = [f"{i+1}. {d}, {m} min, {issue} ({h})" for i,(d,m,issue,h) in enumerate(comment_patches)]

    def remove_comment(_):
        if comment_list.index is not None and comment_list.index >= 0:
            del comment_patches[comment_list.index]
            comment_list.options = [f"{i+1}. {d}, {m} min, {issue} ({h})" for i,(d,m,issue,h) in enumerate(comment_patches)]

    def sync_program(_):
        selected_date = end_date_picker.value.strftime("%Y-%m-%d")
        selected_datetime = f"{selected_date} {end_time_text.value}"
        count = sync_hutch_from_calendar_noics( selected_datetime, period.value, hutch_patches)
        refresh_program_list()
        with out_plot:
            print(f"{count} events synced from {hutch_name.value} calendar")

    def run_report(_):
        with out_plot:
            out_plot.clear_output()
            selected_date = end_date_picker.value.strftime("%Y-%m-%d")
            selected_datetime = f"{selected_date} {end_time_text.value}"
            report_range(selected_datetime, period.value,
                         hutch_patches=hutch_patches,
                         comment_patches=comment_patches)

    add_hutch_btn.on_click(add_hutch)
    remove_hutch_btn.on_click(remove_hutch)
    update_hutch_btn.on_click(update_hutch)
    sync_hutch_btn.on_click(sync_program)
    add_comment_btn.on_click(add_comment)
    remove_comment_btn.on_click(remove_comment)

    run_btn = Button(description="Generate Report", button_style="primary")
    run_btn.on_click(run_report)

    return VBox([
        HBox([end_date_picker, end_time_text, period, sync_hutch_btn]),
        HBox([hutch_date, hutch_minutes, hutch_name, add_hutch_btn, update_hutch_btn, remove_hutch_btn]),
        program_list,
        HBox([comment_date, comment_minutes, comment_hutch, add_comment_btn, remove_comment_btn]),
        HBox([comment_issue]),
        comment_list,
        run_btn,
        out_plot
    ])
