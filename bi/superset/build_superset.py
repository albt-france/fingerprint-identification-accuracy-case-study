"""Create the Superset datasets, charts and dashboard in a LOCAL Superset (run with the .venv-superset interpreter).

    set SUPERSET_CONFIG_PATH=bi/superset/_local/superset_config.py   (local only, secrets in .env)
    .venv-superset/Scripts/python bi/superset/build_superset.py

Then every chart is queried through the Superset chart-data API (test client, local admin) to prove it returns data.
Export afterwards with the CLI: superset export-dashboards -f bi/superset/export/identification_accuracy_dashboard.zip
SIMULATED data only (dbt marts of this case study).
"""
import json
import pathlib

from superset.app import create_app

ROOT = pathlib.Path(__file__).resolve().parents[2]
DS_DIR = ROOT / "bi" / "superset" / "datasets" / "duckdb"
EXPORT = ROOT / "bi" / "superset" / "export"
app = create_app()


def sql_metric(expr, label):
    return {"expressionType": "SQL", "sqlExpression": expr, "label": label}


CHARTS = [
    ("SIMULATED · Platform FP rate: crude vs constant mix vs stable cohort", "ds_mix_standardized", {
        "viz_type": "echarts_timeseries_line", "x_axis": "week_start", "time_grain_sqla": "P1W",
        "metrics": [sql_metric("MAX(fp_rate_crude)", "crude"), sql_metric("MAX(fp_rate_standardized)", "constant mix"),
                    sql_metric("MAX(fp_rate_stable_cohort)", "stable cohort")],
        "groupby": [], "adhoc_filters": [], "row_limit": 1000, "y_axis_format": ".2%", "show_legend": True, "markerEnabled": True}),
    ("SIMULATED · Customer health, latest week", "ds_customer_health", {
        "viz_type": "table", "query_mode": "raw", "all_columns": ["customer_id", "csm_pod", "health_status", "health_reasons", "fp_rate", "fn_rate"],
        "adhoc_filters": [{"clause": "WHERE", "expressionType": "SQL", "sqlExpression": "week_start = DATE '2026-11-16'"}],
        "order_by_cols": [], "row_limit": 100, "percent_metrics": [], "table_timestamp_format": "smart_date",
        "column_config": {"fp_rate": {"d3NumberFormat": ".2%"}, "fn_rate": {"d3NumberFormat": ".2%"}}}),
    ("SIMULATED · Requests by priority and team", "ds_request_queue", {
        "viz_type": "echarts_timeseries_bar", "x_axis": "priority_tier", "metrics": ["count"], "groupby": ["requesting_team"],
        "adhoc_filters": [], "row_limit": 1000, "stack": "Stack", "show_legend": True, "x_axis_sort_asc": True}),
    ("SIMULATED · Requests a self-service tool can answer", "ds_request_queue", {
        "viz_type": "big_number_total", "metric": sql_metric("AVG(CASE WHEN self_service_possible THEN 1.0 ELSE 0 END)", "self-service share"),
        "adhoc_filters": [], "y_axis_format": ".0%", "subheader": "of the 140 simulated requests"}),
]


def build():
    from superset import db
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.core import Database
    from superset.models.dashboard import Dashboard
    from superset.models.slice import Slice

    database = db.session.query(Database).filter_by(database_name="accuracy_duckdb").one()
    tables = {}
    for f in sorted(DS_DIR.glob("*.sql")):
        name = f.stem
        t = db.session.query(SqlaTable).filter_by(table_name=name, database_id=database.id).one_or_none()
        if t is None:
            t = SqlaTable(table_name=name, database=database, schema=None)
            db.session.add(t)
        t.sql = f.read_text(encoding="utf-8")
        t.description = "SIMULATED data (fictional platform and customers). Virtual dataset from bi/superset/datasets/duckdb."
        db.session.flush()
        t.fetch_metadata()
        for col in t.columns:
            if col.column_name in ("week_start", "event_date", "opened_at", "resolved_at", "week_opened"):
                col.is_dttm = True
        tables[name] = t
    db.session.commit()
    slices = []
    for title, ds, params in CHARTS:
        t = tables[ds]
        s = db.session.query(Slice).filter_by(slice_name=title).one_or_none() or Slice(slice_name=title)
        s.viz_type = params["viz_type"]
        s.datasource_type = "table"
        s.datasource_id = t.id
        s.params = json.dumps({**params, "datasource": f"{t.id}__table"})
        db.session.add(s)
        slices.append(s)
    db.session.commit()
    dash = db.session.query(Dashboard).filter_by(slug="identification-accuracy").one_or_none() or Dashboard(slug="identification-accuracy")
    dash.dashboard_title = "Identification accuracy (SIMULATED)"
    dash.slices = slices
    pos = {"DASHBOARD_VERSION_KEY": "v2", "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
           "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW-1", "ROW-2"], "parents": ["ROOT_ID"]},
           "HEADER_ID": {"id": "HEADER_ID", "type": "HEADER", "meta": {"text": "Identification accuracy (SIMULATED)"}}}
    rows = {"ROW-1": slices[:2], "ROW-2": slices[2:]}
    for rid, ss in rows.items():
        pos[rid] = {"type": "ROW", "id": rid, "children": [], "parents": ["ROOT_ID", "GRID_ID"], "meta": {"background": "BACKGROUND_TRANSPARENT"}}
        for s in ss:
            cid = f"CHART-{s.id}"
            pos[rid]["children"].append(cid)
            pos[cid] = {"type": "CHART", "id": cid, "children": [], "parents": ["ROOT_ID", "GRID_ID", rid],
                        "meta": {"chartId": s.id, "width": 6, "height": 60, "sliceName": s.slice_name}}
    dash.position_json = json.dumps(pos)
    dash.json_metadata = json.dumps({"native_filter_configuration": [], "color_scheme": "", "refresh_frequency": 0})
    dash.description = "Independent case study · fictional platform and customers · not Fingerprint data"
    db.session.add(dash)
    db.session.commit()
    return slices, dash.id


def query_for(params, table_id):
    """Chart-data query equivalent to the chart (also saved as the chart's query_context)."""
    vt = params["viz_type"]
    q = {"filters": [], "extras": {"where": " AND ".join(f["sqlExpression"] for f in params.get("adhoc_filters", []))},
         "row_limit": params.get("row_limit", 1000)}
    if vt == "echarts_timeseries_line":
        q.update(columns=[{"columnType": "BASE_AXIS", "sqlExpression": "week_start", "label": "week_start", "expressionType": "SQL"}],
                 metrics=params["metrics"], orderby=[])
    elif vt == "table":
        q.update(columns=params["all_columns"], metrics=[], orderby=[])
    elif vt == "echarts_timeseries_bar":
        q.update(columns=["priority_tier", "requesting_team"], metrics=["count"], orderby=[])
    else:
        q.update(columns=[], metrics=[params["metric"]], orderby=[])
    return {"datasource": {"id": table_id, "type": "table"}, "force": True, "queries": [q], "form_data": params,
            "result_format": "json", "result_type": "full"}


def save_query_contexts(slices):
    from superset import db
    payloads = []
    for s in slices:
        qc = query_for(json.loads(s.params), s.datasource_id)
        s.query_context = json.dumps(qc)
        db.session.add(s)
        payloads.append((s.slice_name, qc))
    db.session.commit()
    return payloads


def check(payloads):
    """Query each chart through the API. Runs OUTSIDE any pushed app context: a shared context keeps the first
    request's user in flask.g and the next requests are refused."""
    env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)
    results = {}
    for name, qc in payloads:
        c = app.test_client()
        tok = c.post("/api/v1/security/login", json={"username": env["SUPERSET_ADMIN_USER"], "password": env["SUPERSET_ADMIN_PASSWORD"],
                                                      "provider": "db", "refresh": False}).get_json()["access_token"]
        r = c.post("/api/v1/chart/data", json=qc, headers={"Authorization": f"Bearer {tok}"})
        body = r.get_json() or {}
        ok = r.status_code == 200
        results[name] = {"status": r.status_code, "rows": sum(x.get("rowcount", 0) for x in body.get("result", [])) if ok else None,
                         "error": None if ok else str(body)[:300]}
    return results


def export(dash_id):
    """Export the dashboard bundle through the API (the CLI export needs a logged-in user) and replace the local
    database path by a placeholder: the importer sets its own connection."""
    import io
    import zipfile
    env = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)
    c = app.test_client()
    tok = c.post("/api/v1/security/login", json={"username": env["SUPERSET_ADMIN_USER"], "password": env["SUPERSET_ADMIN_PASSWORD"],
                                                  "provider": "db", "refresh": False}).get_json()["access_token"]
    r = c.get(f"/api/v1/dashboard/export/?q=!({dash_id})", headers={"Authorization": f"Bearer {tok}"})
    r.raise_for_status() if hasattr(r, "raise_for_status") else None
    EXPORT.mkdir(parents=True, exist_ok=True)
    out = EXPORT / "identification_accuracy_dashboard.zip"
    with zipfile.ZipFile(io.BytesIO(r.data)) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename).replace(str(ROOT / "dbt").replace("\\", "/").encode(), b"/path/to/dbt")
            data = data.replace(b"C:/case-study-fingerprint/dbt", b"/path/to/dbt")
            zout.writestr(item.filename, data)
    print("export:", r.status_code, out.name)


if __name__ == "__main__":
    with app.app_context():
        slices, did = build()
        payloads = save_query_contexts(slices)
    res = check(payloads)
    (ROOT / "bi" / "superset" / "chart_check.json").write_text(json.dumps(res, indent=1))
    export(did)
    print(json.dumps({"charts": res, "dashboard_id": did}, indent=1))
