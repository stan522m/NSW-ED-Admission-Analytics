import os
import duckdb
import pandas as pd

# Configuration constants
DB_FILE = "nsw_healthcare_analytics.db"
CSV_PATH = "bhi_ed_q2_2026.csv"

def run_pipeline():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"Could not find '{CSV_PATH}' in the project directory.")
    
    print(f"[*] Reading official BHI data from {CSV_PATH}...")
    df_raw = pd.read_csv(CSV_PATH, encoding='cp1252')
    
    # 1. Clean column names
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    
    # 2. Filter strictly for individual hospital-level rows using reporting_level
    rep_col = 'reporting_level'
    print(f"[*] Filtering rows where {rep_col} == 'Hospital'...")
    df_hospitals = df_raw[df_raw[rep_col].astype(str).str.lower() == 'hospital'].copy()
    print(f"[*] Found {len(df_hospitals)} hospital-level metric rows.")

    # 3. Clean measure_value
    df_hospitals['measure_value'] = pd.to_numeric(
        df_hospitals['measure_value'].astype(str).str.replace(',', '').str.strip(), 
        errors='coerce'
    )
    
    print("[*] Pivoting long-format hospital metrics into wide schema...")
    
    # 4. Pivot the long-format rows into wide columns
    df_wide = df_hospitals.pivot_table(
        index=['entity_id', 'entity_longname', 'entity_shortname', 'lhd_shortname', 'peer_group_shortname', 'reporting_period'],
        columns='measure_name',
        values='measure_value',
        aggfunc='first'
    ).reset_index()
    
    # 5. Clean column names to standard snake_case
    df_wide.columns.name = None
    df_wide.columns = (
        df_wide.columns.str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('(%|%)', 'pct', regex=True)
        .str.replace(r'[^\w\s]', '_', regex=True)
    )
    
    # Standardize primary identifiers & measure names to match app.py
    df_wide = df_wide.rename(columns={
        'entity_longname': 'hospital_name',
        'lhd_shortname': 'lhd_name',
        'peer_group_shortname': 'peer_group',
        'reporting_period': 'quarter',
        'emergency_presentations': 'ed_presentations',
        'percentage_of_patients_starting_treatment_on_time': 'patients_within_4hrs_pct',
        '90th_percentile_time_to_transfer_care_from_paramedics_to_ed_staff': 'p90_paramedic_transfer_minutes'
    })

    # 6. Connect to DuckDB and load the table
    print(f"[*] Connecting to DuckDB database: {DB_FILE}...")
    con = duckdb.connect(database=DB_FILE, read_only=False)
    
    con.execute("DROP TABLE IF EXISTS nsw_hospital_performance;")
    con.execute("CREATE TABLE nsw_hospital_performance AS SELECT * FROM df_wide;")
    print(f"[+] Successfully loaded {len(df_wide)} hospitals with full wide metrics into DuckDB!")
    
    # 7. Export full wide results to CSV for review
    output_csv = "hospital_wait_rankings.csv"
    df_wide.to_csv(output_csv, index=False)
    print(f"[+] Successfully exported wide dataset to '{output_csv}'!")
    
    # 8. Verify table structure and preview top rows
    print("\n[*] Table Structure (DESCRIBE):")
    print(con.execute("DESCRIBE nsw_hospital_performance;").fetchdf())

    con.close()
    print("\n[+] Pipeline completed successfully!")

if __name__ == "__main__":
    run_pipeline()