"""Generate grafana/dashboards/dora.json.

The dashboard is built from code rather than hand-edited JSON so the SQL
stays readable and reviewable. Re-run after changing it:

    uv run python grafana/build_dashboard.py
"""

import json
from pathlib import Path

DATASOURCE = {"type": "grafana-postgresql-datasource", "uid": "dora-postgres"}
WHERE = "repo = '$repo' and environment = '$environment'"


def target(sql: str) -> dict:
    return {
        "datasource": DATASOURCE,
        "refId": "A",
        "rawQuery": True,
        "format": "table",
        "editorMode": "code",
        "rawSql": " ".join(sql.split()),
    }


def stat(id_, title, description, sql, unit, x, decimals=None, thresholds=None):
    defaults = {
        "unit": unit,
        "color": {"mode": "thresholds"},
        "thresholds": {
            "mode": "absolute",
            "steps": thresholds or [{"color": "blue", "value": None}],
        },
    }
    if decimals is not None:
        defaults["decimals"] = decimals
    return {
        "id": id_,
        "type": "stat",
        "title": title,
        "description": description,
        "datasource": DATASOURCE,
        "gridPos": {"h": 5, "w": 6, "x": x, "y": 0},
        "targets": [target(sql)],
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "colorMode": "background",
            "graphMode": "none",
            "textMode": "value",
        },
    }


def timeseries(id_, title, sql, unit, x, y, bars=False):
    custom = {
        "drawStyle": "bars" if bars else "line",
        "fillOpacity": 80 if bars else 10,
        "lineWidth": 2,
        "pointSize": 6,
        "showPoints": "always",
        "spanNulls": True,
    }
    if bars:
        custom["stacking"] = {"mode": "normal", "group": "A"}
    return {
        "id": id_,
        "type": "timeseries",
        "title": title,
        "datasource": DATASOURCE,
        "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
        "targets": [{**target(sql), "format": "time_series"}],
        "fieldConfig": {"defaults": {"unit": unit, "custom": custom}, "overrides": []},
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi"},
        },
    }


def variable(name, label, sql):
    return {
        "name": name,
        "label": label,
        "type": "query",
        "datasource": DATASOURCE,
        "query": sql,
        "definition": sql,
        "refresh": 1,
        "sort": 1,
        "current": {},
        "options": [],
        "includeAll": False,
        "multi": False,
    }


# Keep every week that overlaps the range, not only weeks that start inside it,
# and plot a partial first week at the range start so it isn't clipped.
WEEK = "greatest(week::timestamptz, $__timeFrom()::timestamptz)"
weekly = f"""from weekly_metrics where {WHERE}
             and week::timestamptz + interval '7 days' > $__timeFrom()::timestamptz
             and week::timestamptz < $__timeTo()::timestamptz order by 1"""

dashboard = {
    "uid": "dora",
    "title": "DORA metrics",
    "description": "Deployment frequency, lead time, change failure rate and recovery time.",
    "tags": ["dora"],
    "timezone": "utc",
    "schemaVersion": 41,
    "time": {"from": "now-90d", "to": "now"},
    "refresh": "",
    "templating": {
        "list": [
            variable("repo", "Repo", "select distinct repo from deployments order by 1"),
            variable(
                "environment",
                "Environment",
                "select distinct environment from deployments where repo = '$repo' order by 1",
            ),
        ]
    },
    "panels": [
        stat(
            1,
            "Deployments per week",
            "Successful deployments in the selected time range, per week.",
            f"""select count(*) / greatest(extract(epoch from
                 ($__timeTo()::timestamptz - $__timeFrom()::timestamptz)) / 604800, 1e-9)
                 as "Deployments per week"
                 from deployments where {WHERE} and state = 'success'
                 and $__timeFilter(finished_at)""",
            "none",
            0,
            decimals=1,
        ),
        stat(
            2,
            "Lead time for changes",
            "Median time from a PR's first commit to the deployment that shipped it.",
            f"""select percentile_cont(0.5) within group (order by lead_time_hours) * 3600
                 as "Median lead time"
                 from lead_times where {WHERE} and $__timeFilter(deployed_at)""",
            "s",
            6,
        ),
        stat(
            3,
            "Change failure rate",
            "Share of finished deployments that failed.",
            f"""select avg((state <> 'success')::int) as "Change failure rate"
                 from deployments where {WHERE} and $__timeFilter(finished_at)""",
            "percentunit",
            12,
            thresholds=[
                {"color": "green", "value": None},
                {"color": "orange", "value": 0.15},
                {"color": "red", "value": 0.3},
            ],
        ),
        stat(
            4,
            "Recovery time",
            "Median time from a failed deployment to the next successful one.",
            f"""select percentile_cont(0.5) within group (order by recovery_hours) * 3600
                 as "Median recovery time"
                 from recoveries where {WHERE} and $__timeFilter(recovered_at)""",
            "s",
            18,
        ),
        timeseries(
            5,
            "Deployments per week",
            f"""select {WEEK} as time, deployments as "Succeeded",
                       failed as "Failed" {weekly}""",
            "none",
            0,
            5,
            bars=True,
        ),
        timeseries(
            6,
            "Lead time for changes (weekly median)",
            f"""select {WEEK} as time,
                       median_lead_time_hours * 3600 as "Lead time" {weekly}""",
            "s",
            12,
            5,
        ),
        timeseries(
            7,
            "Change failure rate (weekly)",
            f"""select {WEEK} as time,
                       change_failure_rate as "Change failure rate" {weekly}""",
            "percentunit",
            0,
            13,
        ),
        timeseries(
            8,
            "Recovery time (weekly median)",
            f"""select {WEEK} as time,
                       median_recovery_hours * 3600 as "Recovery time" {weekly}""",
            "s",
            12,
            13,
        ),
    ],
}

out = Path(__file__).parent / "dashboards" / "dora.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(dashboard, indent=2) + "\n")
print(f"Wrote {out}")
