# db_viewer.py
# UI Framework Choice: Shiny for Python
# Reasoning: Shiny is browser-based, offering better scalability and accessibility for interactive data visualization and sharing.

import sqlite3
import pandas as pd
import plotly.express as px
from shiny import App, ui, render, reactive, req
import os

def get_artifacts_for_run(run_id):
    conn = sqlite3.connect(DB_NAME)
    query = f"SELECT file_name, file_path FROM artifacts WHERE run_id = {run_id}"
    artifacts_df = pd.read_sql_query(query, conn)
    conn.close()
    return artifacts_df

# --- CONFIGURATION ---
DB_NAME = "prompt_compare.db"

# --- DATA ACCESS FUNCTIONS ---
def get_all_runs():
    print("Fetching all runs from DB...")
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT id, run_date, cor_file_id FROM runs ORDER BY run_date DESC"
    runs_df = pd.read_sql_query(query, conn)
    conn.close()
    print(f"Found {len(runs_df)} runs.")
    runs_df['display_name'] = runs_df.apply(lambda row: f"Run {row['id']} - {row['run_date']} ({row['cor_file_id']})", axis=1)
    return runs_df

def get_metrics_for_run(run_id):
    conn = sqlite3.connect(DB_NAME)
    query = f"SELECT * FROM metrics WHERE run_id = {run_id}"
    metrics_df = pd.read_sql_query(query, conn)
    conn.close()
    return metrics_df

def get_all_metrics():
    conn = sqlite3.connect(DB_NAME)
    query = "SELECT r.run_date, r.cor_file_id, m.* FROM runs r JOIN metrics m ON r.id = m.run_id ORDER BY r.run_date ASC"
    all_metrics_df = pd.read_sql_query(query, conn)
    conn.close()
    return all_metrics_df

# --- SHINY UI ---
app_ui = ui.page_fluid(
    ui.h2("Prompt Compare Results Viewer"),
    ui.page_sidebar(
        ui.sidebar(
            ui.input_select("selected_run", "Select Run", {}),
            ui.input_action_button("refresh_data", "Refresh Data"),
            ui.hr(),
            ui.h4("Trend Analysis Options"),
            ui.input_select("trend_metric", "Select Metric for Trend",
                            {
                                "final_relevance_score": "Final Relevance Score",
                                "reading_level": "Reading Level",
                                "word_count": "Word Count",
                                "llm_relevance_score": "LLM Relevance Score",
                                "cosine_similarity_score": "Cosine Similarity Score",
                                "metric_alignment_score": "Metric Alignment Score",
                                "data_relevance_score": "Data Relevance Score",
                                "primer_consistency_score": "Primer Consistency Score",
                                "structure_score": "Structure Score",
                                "clarity_score": "Clarity Score",
                                "writing_quality_score": "Writing Quality Score",
                                "composite_score": "Composite Score"
                            }),
        ),
        ui.h3("Metric Comparison for Selected Run"),
        ui.output_ui("metric_comparison_table"),
        ui.hr(),
        ui.h3("Metric Trend Over Time"),
        ui.output_ui("metric_trend_plot"),
    ),
)

# --- SHINY SERVER ---
def server(input, output, session):

    def update_runs_data():
        print("Attempting to update runs...")
        runs_df = get_all_runs()
        print(f"Runs DataFrame loaded: {not runs_df.empty}")
        if not runs_df.empty:
            print(f"First run ID: {runs_df['id'].iloc[0]}")
            ui.update_select("selected_run", choices=dict(zip(runs_df['id'], runs_df['display_name'])), selected=int(runs_df['id'].iloc[0]))
        else:
            ui.update_select("selected_run", choices={{}}, selected=None)
        print("Runs update complete.")

    # Initial load
    update_runs_data()

    @reactive.event(input.refresh_data, ignore_init=True)
    def refresh_observer():
        update_runs_data()

    @render.ui
    def metric_comparison_table():
        selected_run_id = input.selected_run()
        if not selected_run_id:
            return ui.p("Please select a run.")
        metrics_df = get_metrics_for_run(selected_run_id)
        artifacts_df = get_artifacts_for_run(selected_run_id)
        
        if metrics_df.empty:
            return ui.p("No metrics found for this run.")

        # Pivot table for side-by-side comparison
        comparison_data = {
            "Metric": [],
            "Summary A": [],
            "Summary B": []
        }

        for metric_name in [
            'reading_level', 'word_count', 'llm_relevance_score', 'cosine_similarity_score', 'final_relevance_score',
            'metric_alignment_score', 'data_relevance_score', 'primer_consistency_score', 'structure_score',
            'clarity_score', 'writing_quality_score', 'composite_score'
        ]:
            comparison_data["Metric"].append(metric_name.replace('_', ' ').title())
            comparison_data["Summary A"].append(metrics_df[metrics_df['summary_type'] == 'A'][metric_name].iloc[0] if not metrics_df[metrics_df['summary_type'] == 'A'].empty else "N/A")
            comparison_data["Summary B"].append(metrics_df[metrics_df['summary_type'] == 'B'][metric_name].iloc[0] if not metrics_df[metrics_df['summary_type'] == 'B'].empty else "N/A")
        
        # Add relevance justification separately as it's text
        comparison_data["Metric"].append("Relevance Justification")
        comparison_data["Summary A"].append(metrics_df[metrics_df['summary_type'] == 'A']['relevance_justification'].iloc[0].replace('\n', '<br>') if not metrics_df[metrics_df['summary_type'] == 'A'].empty else "N/A")
        comparison_data["Summary B"].append(metrics_df[metrics_df['summary_type'] == 'B']['relevance_justification'].iloc[0].replace('\n', '<br>') if not metrics_df[metrics_df['summary_type'] == 'B'].empty else "N/A")

        # Add notes separately
        for note_name in [
            'metric_alignment_note', 'data_relevance_note', 'primer_consistency_note', 'structure_note',
            'clarity_note', 'writing_quality_note'
        ]:
            comparison_data["Metric"].append(note_name.replace('_', ' ').title())
            comparison_data["Summary A"].append(metrics_df[metrics_df['summary_type'] == 'A'][note_name].iloc[0] if not metrics_df[metrics_df['summary_type'] == 'A'].empty else "N/A")
            comparison_data["Summary B"].append(metrics_df[metrics_df['summary_type'] == 'B'][note_name].iloc[0] if not metrics_df[metrics_df['summary_type'] == 'B'].empty else "N/A")

        # Add summary file paths
        if not artifacts_df.empty:
            summary_a_path = artifacts_df[artifacts_df['file_name'].str.contains('summary_A')]['file_path'].iloc[0]
            summary_b_path = artifacts_df[artifacts_df['file_name'].str.contains('summary_B')]['file_path'].iloc[0]

            comparison_data["Metric"].append("Summary File")
            comparison_data["Summary A"].append(os.path.basename(summary_a_path))
            comparison_data["Summary B"].append(os.path.basename(summary_b_path))

            comparison_data["Metric"].append("File Path")
            comparison_data["Summary A"].append(summary_a_path)
            comparison_data["Summary B"].append(summary_b_path)

        comparison_df = pd.DataFrame(comparison_data)
        return ui.HTML(comparison_df.to_html(index=False, escape=False))

    @render.ui
    def metric_trend_plot():
        print(f"metric_trend_plot called with trend_metric: {input.trend_metric()}")
        req(input.trend_metric)
        all_metrics_df = get_all_metrics()
        
        if all_metrics_df.empty:
            return ui.p("No data for trend analysis.")

        # Ensure run_date is datetime for proper sorting and plotting
        all_metrics_df['run_date'] = pd.to_datetime(all_metrics_df['run_date'])
        
        trend_metric_val = input.trend_metric()
        # Filter for the selected metric
        plot_df = all_metrics_df[['run_date', 'summary_type', trend_metric_val]]
        
        fig = px.line(plot_df, 
                      x="run_date", 
                      y=trend_metric_val, 
                      color="summary_type",
                      title=f"{trend_metric_val.replace('_', ' ').title()} Trend Over Time",
                      labels={
                          "run_date": "Run Date",
                          trend_metric_val: trend_metric_val.replace('_', ' ').title(),
                          "summary_type": "Summary Type"
                      })
        fig.update_layout(hovermode="x unified")
        return ui.HTML(fig.to_html())


app = App(app_ui, server)
