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

# --- ics 파싱 ---
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
                # tz 처리
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

# --- PV 데이터 불러오기 ---
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

# --- 리포트/플롯 ---
def report_range(end_date: str, period: str, hutch_patches=[], comment_patches=[], threshold=None):
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

    gmd_df = fetch_pv_data_as_df(epics_pvs["GMD"][0], start_time, end_time).iloc[::5]
    xgmd_df = fetch_pv_data_as_df(epics_pvs["XGMD"][0], start_time, end_time).iloc[::5]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15,8), sharex=False)

    ax1.plot(gmd_df["Timestamp"], gmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["GMD"][1], label="GMD")
    ax1.set_ylabel("GMD (mJ)")
    ax1.set_title(f"Report {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
    ax1.grid(True)
    ax1.set_ylim([-0.4, 3])
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=tz))

    ax2.plot(xgmd_df["Timestamp"], xgmd_df["Value1"], 'o', alpha=0.1, ms=1,
             color=epics_pvs["XGMD"][1], label="XGMD")
    ax2.set_xlabel("Time")
    ax2.set_ylabel("XGMD (mJ)")
    ax2.grid(True)
    ax2.set_ylim([-0.4, 3])
    ax2.set_xlim(ax1.get_xlim())
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M', tz=tz))
    fig.autofmt_xdate()

    patch_ymin, patch_ymax = -0.4, -0.2
    comment_patch_ymin, comment_patch_ymax = 0, 3
    table_data = []

    for ax in [ax1, ax2]:
        for start_str, minutes, hutch in hutch_patches:
            start_patch = tz.localize(datetime.strptime(start_str, "%Y-%m-%d %H:%M"))
            end_patch = start_patch + timedelta(minutes=minutes)
            if start_dt <= end_patch and end_dt >= start_patch:
                color = hutch_colors.get(hutch, 'gray')
                ax.fill_betweenx([patch_ymin, patch_ymax], start_patch, end_patch, color=color, alpha=0.8)

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

    result_html = ""
    if threshold is not None:
        below = gmd_df[gmd_df["Value1"] < threshold]
        above = gmd_df[gmd_df["Value1"] >= threshold]
        dt = gmd_df["Timestamp"].diff().median().total_seconds() if len(gmd_df) > 1 else 0
        below_minutes = len(below) * dt / 60
        above_minutes = len(above) * dt / 60
        result_html = f"<b>GMD Threshold {threshold} mJ:</b><br>Below: {below_minutes:.1f} min<br>Above: {above_minutes:.1f} min"

    return result_html

# --- GUI ---
def report_gui():
    end_date_picker = DatePicker(value=datetime.today().date(), description="End date")
    end_time_text = Text(value="06:00:00", description="Time")
    period = Dropdown(options=["1d","7d","8d","9d","14d"], value="7d", description="Period")

    # Hutch patch 입력/리스트
    hutch_list_widget = Select(options=[], rows=6, description="Hutch List", layout=widgets.Layout(width="600px"))
    comment_list_widget = Select(options=[], rows=4, description="Comments", layout=widgets.Layout(width="600px"))

    # GMD Threshold
    threshold_input = FloatText(value=0.1, description="GMD Threshold (mJ)")
    threshold_output = HTML()
    out_plot = Output()

    # --- 자동 허치 로드 ---
    tz = pytz.timezone("America/Los_Angeles")
    today = datetime.now(tz)
    start_window = today - timedelta(days=7)
    end_window   = today + timedelta(days=14)

    hutch_patches = []
    for hutch, url in hutch_calendars.items():
        hutch_patches.extend(load_hutch_patches(hutch, url, start_dt=start_window, end_dt=end_window))

    hutch_list_widget.options = [f"{s}, {m} min, {h}" for s,m,h in hutch_patches]

    # --- Run report 콜백 ---
    def run_report(_):
        with out_plot:
            out_plot.clear_output()
            selected_date = end_date_picker.value.strftime("%Y-%m-%d")
            selected_datetime = f"{selected_date} {end_time_text.value}"
            result_html = report_range(
                selected_datetime, period.value,
                hutch_patches=hutch_patches,
                comment_patches=[],   # 수동 comment만
                threshold=threshold_input.value
            )
            threshold_output.value = result_html

    run_btn = Button(description="Generate Report", button_style="primary")
    run_btn.on_click(run_report)

    return VBox([
        HBox([end_date_picker, end_time_text, period]),
        threshold_input,
        hutch_list_widget,
        comment_list_widget,
        run_btn,
        out_plot,
        threshold_output
    ])
