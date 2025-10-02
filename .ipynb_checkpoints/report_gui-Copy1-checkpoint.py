import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import requests, io, pytz

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
    "MD" : "gray",
}

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

    # --- Fetch PVs ---
    gmd_df = fetch_pv_data_as_df(epics_pvs["GMD"][0], start_time, end_time).iloc[::5]
    xgmd_df = fetch_pv_data_as_df(epics_pvs["XGMD"][0], start_time, end_time).iloc[::5]

    # --- Plot ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8), sharex=False)

    # GMD
    ax1.plot(gmd_df["Timestamp"], gmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["GMD"][1], label="GMD")
    ax1.set_ylabel("HXR Pulse Energy(mJ)")
    ax1.set_title(f"Report {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
    ax1.grid(True)
    ax1.set_ylim([-0.4, 3])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=tz))

    # XGMD
    ax2.plot(xgmd_df["Timestamp"], xgmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["XGMD"][1], label="XGMD")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("SXR Pulse Energy(mJ)")
    ax2.grid(True)
    ax2.set_ylim([-0.4, 3])
    ax2.set_xlim(ax1.get_xlim())

    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=tz))
    fig.autofmt_xdate()

    patch_ymin, patch_ymax = -0.4, -0.2
    comment_patch_ymin, comment_patch_ymax = 0, 3
    table_data = []

    for ax in [ax1, ax2]:
        # Hutch patches
        for start_str, minutes, hutch in hutch_patches:
            start_patch = tz.localize(datetime.strptime(start_str, "%Y-%m-%d %H:%M"))
            end_patch = start_patch + timedelta(minutes=minutes)
            if start_dt <= end_patch and end_dt >= start_patch:
                color = hutch_colors.get(hutch, 'gray')
                ax.fill_betweenx([patch_ymin, patch_ymax], start_patch, end_patch, color=color, alpha=0.8)

        # Comment patches
        sorted_comments = sorted(comment_patches,
            key=lambda x: tz.localize(datetime.strptime(x[0], "%Y-%m-%d %H:%M"))
        )
        for i, (start_str, minutes, issue, hutch) in enumerate(sorted_comments, start=1):
            start_comment = tz.localize(datetime.strptime(start_str, "%Y-%m-%d %H:%M"))
            end_comment = start_comment + timedelta(minutes=minutes)
            if start_dt <= end_comment and end_dt >= start_comment:
                ax.fill_betweenx([comment_patch_ymin, comment_patch_ymax],
                                 start_comment, end_comment,
                                 color='gray', alpha=0.2)
                ax.text(start_comment + (end_comment - start_comment)/2,
                        comment_patch_ymin + 0.7*(comment_patch_ymax - comment_patch_ymin),
                        str(i), ha='center', va='center', fontsize=10, fontweight='bold')
                if ax is ax2: 
                    table_data.append([i, start_str, minutes, issue, hutch])
    if table_data:
        table = ax2.table(cellText=table_data,
                         colLabels=["#", "Start", "Minutes", "Issue", "Area"],
                         cellLoc='center', colLoc='center',
                         loc='bottom', bbox=[0, -0.5, 1, 0.35])
        table.auto_set_font_size(False)
        table.set_fontsize(10)

    plt.show()


def report_gui():
    # --- End date/time ---
    end_date_picker = DatePicker(
        value=datetime.today().date(),
        description="End date"
    )
    end_time_text = Text(value="06:00:00", description="Time")

    period = Dropdown(options=["1d","7d","8d","9d","14d"], value="7d", description="Period")

    # Range multi-add inputs
    range_start = Text(value="2025-09-02", description="Start Date")
    range_end = Text(value="2025-09-06", description="End Date")
    range_time = Text(value="06:00", description="Time")
    range_minutes = IntText(value=720, description="Minutes")
    range_hutch = Dropdown(options=list(hutch_colors.keys()), value="XCS", description="Hutch")
    add_range_btn = Button(description="Add Range", button_style="info")

    # Hutch patch inputs
    hutch_date = Text(value="2025-09-02 06:00", description="Start")
    hutch_minutes = IntText(value=720, description="Minutes")
    hutch_name = Dropdown(options=list(hutch_colors.keys()), value="XCS", description="Hutch")
    add_hutch_btn = Button(description="Add Hutch", button_style="success")
    remove_hutch_btn = Button(description="Remove", button_style="danger")
    update_hutch_btn = Button(description="Update", button_style="warning")
    hutch_list = Select(options=[], rows=6, description="Hutch List",layout=widgets.Layout(width="600px"))

    # Comment inputs
    comment_date = Text(value="2025-09-03 09:15", description="Start")
    comment_minutes = IntText(value=60, description="Minutes")
    comment_issue = Text(value="Shutter delay", description="Issue")
    comment_hutch = Dropdown(options=list(hutch_colors.keys()), value="CXI", description="Hutch")
    add_comment_btn = Button(description="Add Comment", button_style="info")
    remove_comment_btn = Button(description="Remove", button_style="danger")
    comment_list = Select(options=[], rows=4, description="Comments",layout=widgets.Layout(width="600px"))

    out_plot = widgets.Output()

    hutch_patches = []
    comment_patches = []

    # --- Callbacks ---
    def refresh_hutch_list():
        hutch_list.options = [f"{i+1}. {d}, {m} min, {h}" for i,(d,m,h) in enumerate(hutch_patches)]

    def add_hutch(_):
        hutch_patches.append((hutch_date.value, hutch_minutes.value, hutch_name.value))
        refresh_hutch_list()

    def remove_hutch(_):
        if hutch_list.index is not None and hutch_list.index >= 0:
            del hutch_patches[hutch_list.index]
            refresh_hutch_list()

    # def update_hutch(_):
    #     if hutch_list.index is not None and hutch_list.index >= 0:
    #         hutch_patches[hutch_list.index] = (hutch_date.value, hutch_minutes.value, hutch_name.value)
    #         refresh_hutch_list()
    def update_hutch(_):
        if hutch_list.value:  
            idx = hutch_list.options.index(hutch_list.value)
            hutch_patches[idx] = (hutch_date.value, hutch_minutes.value, hutch_name.value)
            refresh_hutch_list()
    
    def on_hutch_select(change):
        if change["new"]:
            idx = hutch_list.options.index(change["new"])
            date, minutes, hutch = hutch_patches[idx]
            hutch_date.value = date
            hutch_minutes.value = minutes
            hutch_name.value = hutch

    hutch_list.observe(on_hutch_select, names="value")


    def add_range(_):
        start = datetime.strptime(range_start.value, "%Y-%m-%d")
        end = datetime.strptime(range_end.value, "%Y-%m-%d")
        time_str = range_time.value
        minutes = range_minutes.value
        hutch = range_hutch.value

        curr = start
        while curr <= end:
            dt_str = f"{curr.strftime('%Y-%m-%d')} {time_str}"
            hutch_patches.append((dt_str, minutes, hutch))
            curr += timedelta(days=1)
        refresh_hutch_list()

    def add_comment(_):
        comment_patches.append((comment_date.value, comment_minutes.value, comment_issue.value, comment_hutch.value))
        comment_list.options = [f"{i+1}. {d}, {m} min, {issue} ({h})" for i,(d,m,issue,h) in enumerate(comment_patches)]

    def remove_comment(_):
        if comment_list.index is not None and comment_list.index >= 0:
            del comment_patches[comment_list.index]
            comment_list.options = [f"{i+1}. {d}, {m} min, {issue} ({h})" for i,(d,m,issue,h) in enumerate(comment_patches)]

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
    add_range_btn.on_click(add_range)
    add_comment_btn.on_click(add_comment)
    remove_comment_btn.on_click(remove_comment)

    run_btn = Button(description="Generate Report", button_style="primary")
    run_btn.on_click(run_report)

    return VBox([
        HBox([end_date_picker, end_time_text, period]),
        HBox([range_start, range_end, range_time, range_minutes, range_hutch, add_range_btn]),
        HBox([hutch_date, hutch_minutes, hutch_name, add_hutch_btn, update_hutch_btn, remove_hutch_btn]),
        hutch_list,
        HBox([comment_date, comment_minutes, comment_issue, comment_hutch, add_comment_btn, remove_comment_btn]),
        comment_list,
        run_btn,
        out_plot
    ])
