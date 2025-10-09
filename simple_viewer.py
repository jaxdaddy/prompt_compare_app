# simple_viewer.py
import sqlite3
import pandas as pd
from shiny import App, ui, render

# --- CONFIGURATION ---
DB_NAME = "prompt_compare.db"

# --- DATA ACCESS FUNCTIONS ---
def get_table_data(table_name):
    try:
        conn = sqlite3.connect(DB_NAME)
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error reading from database: {e}")
        return pd.DataFrame()

# --- SHINY UI ---
app_ui = ui.page_fluid(
    ui.h2("Simple Database Viewer"),
    ui.h3("Runs Table"),
    ui.output_data_frame("runs_table"),
    ui.h3("Metrics Table"),
    ui.output_data_frame("metrics_table"),
)

# --- SHINY SERVER ---
def server(input, output, session):
    @render.data_frame
    def runs_table():
        return get_table_data("runs")

    @render.data_frame
    def metrics_table():
        return get_table_data("metrics")

app = App(app_ui, server)
