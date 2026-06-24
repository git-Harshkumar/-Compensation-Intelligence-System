from __future__ import annotations

import math
import sqlite3
from statistics import median
from typing import Any

from server.database import row, rows
from server.security import now_iso


def reference_data(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    return {
        "roleFamilies": rows(conn, "SELECT * FROM role_families ORDER BY name"),
        "levels": rows(conn, "SELECT * FROM levels ORDER BY rank"),
        "locations": rows(conn, "SELECT * FROM locations ORDER BY region, name"),
    }


def _record_query(filters: dict[str, str]) -> tuple[str, list[Any]]:
    query = """
        SELECT cr.*, rf.slug role_slug, rf.name role_name, l.code level_code, l.name level_name,
               l.rank level_rank, loc.slug location_slug, loc.name location_name,
               c.name company_name, c.stage company_stage, c.size_band company_size
        FROM compensation_records cr
        JOIN role_families rf ON rf.id = cr.role_family_id
        JOIN levels l ON l.id = cr.level_id
        JOIN locations loc ON loc.id = cr.location_id
        JOIN companies c ON c.id = cr.company_id
        WHERE 1 = 1
    """
    params: list[Any] = []
    if filters.get("role"):
        query += " AND rf.slug = ?"
        params.append(filters["role"])
    if filters.get("level"):
        query += " AND l.code = ?"
        params.append(filters["level"])
    if filters.get("location"):
        query += " AND loc.slug = ?"
        params.append(filters["location"])
    return query + " ORDER BY cr.effective_date DESC", params


def _percentile(values: list[int], percentile: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    k = (len(ordered) - 1) * percentile
    floor = math.floor(k)
    ceil = math.ceil(k)
    if floor == ceil:
        return int(ordered[floor])
    return int(ordered[floor] * (ceil - k) + ordered[ceil] * (k - floor))


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals = [r["base_salary"] + r["bonus"] + r["equity_annual_value"] for r in records]
    bases = [r["base_salary"] for r in records]
    bonuses = [r["bonus"] for r in records]
    equities = [r["equity_annual_value"] for r in records]
    return {
        "count": len(records),
        "p25": _percentile(totals, 0.25),
        "median": int(median(totals)) if totals else 0,
        "p75": _percentile(totals, 0.75),
        "baseMedian": int(median(bases)) if bases else 0,
        "bonusMedian": int(median(bonuses)) if bonuses else 0,
        "equityMedian": int(median(equities)) if equities else 0,
        "baseShare": round((int(median(bases)) / int(median(totals))) * 100, 1) if totals and int(median(totals)) else 0,
        "bonusShare": round((int(median(bonuses)) / int(median(totals))) * 100, 1) if totals and int(median(totals)) else 0,
        "equityShare": round((int(median(equities)) / int(median(totals))) * 100, 1) if totals and int(median(totals)) else 0,
        "confidence": round(sum(r["confidence_score"] for r in records) / len(records), 2) if records else 0,
    }


def benchmark(conn: sqlite3.Connection, filters: dict[str, str]) -> dict[str, Any]:
    query, params = _record_query(filters)
    records = rows(conn, query, params)
    summary = summarize(records)
    return {"summary": summary, "records": records[:50]}


def compare(conn: sqlite3.Connection, cohorts: list[dict[str, str]]) -> dict[str, Any]:
    results = []
    for index, cohort in enumerate(cohorts):
        data = benchmark(conn, cohort)
        label = " / ".join(value for value in (cohort.get("level"), cohort.get("role"), cohort.get("location")) if value)
        results.append({"id": index + 1, "label": label or f"Cohort {index + 1}", "filters": cohort, **data})

    baseline = results[0]["summary"]["median"] if results and results[0]["summary"]["median"] else 0
    for result in results:
        median_value = result["summary"]["median"]
        result["deltaFromBaseline"] = median_value - baseline if baseline else 0
        result["deltaPercent"] = round(((median_value - baseline) / baseline) * 100, 1) if baseline else 0
    return {"cohorts": results}


def level_matrix(conn: sqlite3.Connection, role: str, location: str) -> dict[str, Any]:
    levels = rows(conn, "SELECT code, name, rank, scope FROM levels ORDER BY rank")
    cohorts = []
    previous_median = 0
    for level in levels:
        data = benchmark(conn, {"role": role, "level": level["code"], "location": location})
        median_value = data["summary"]["median"]
        cohorts.append(
            {
                "level": level,
                "summary": data["summary"],
                "stepUp": median_value - previous_median if previous_median else 0,
                "stepUpPercent": round(((median_value - previous_median) / previous_median) * 100, 1)
                if previous_median
                else 0,
            }
        )
        if median_value:
            previous_median = median_value
    return {"role": role, "location": location, "levels": cohorts}


def location_adjustment(conn: sqlite3.Connection, role: str, level: str) -> dict[str, Any]:
    locations = rows(conn, "SELECT slug, name, region, market_multiplier FROM locations ORDER BY region, name")
    cohorts = []
    for location in locations:
        data = benchmark(conn, {"role": role, "level": level, "location": location["slug"]})
        cohorts.append({"location": location, "summary": data["summary"]})
    baseline = next((item["summary"]["median"] for item in cohorts if item["location"]["slug"] == "remote-us"), 0)
    for item in cohorts:
        median_value = item["summary"]["median"]
        item["deltaFromRemote"] = median_value - baseline if baseline else 0
        item["deltaPercent"] = round(((median_value - baseline) / baseline) * 100, 1) if baseline else 0
    return {"role": role, "level": level, "locations": cohorts}


def structure_insights(conn: sqlite3.Connection, role: str, level: str, location: str) -> dict[str, Any]:
    data = benchmark(conn, {"role": role, "level": level, "location": location})
    records = data["records"]
    mixes = []
    for record in records:
        total = record["base_salary"] + record["bonus"] + record["equity_annual_value"]
        mixes.append(
            {
                "companyName": record["company_name"],
                "stage": record["company_stage"],
                "sizeBand": record["company_size"],
                "total": total,
                "baseShare": round(record["base_salary"] / total * 100, 1) if total else 0,
                "bonusShare": round(record["bonus"] / total * 100, 1) if total else 0,
                "equityShare": round(record["equity_annual_value"] / total * 100, 1) if total else 0,
            }
        )
    return {"summary": data["summary"], "mixes": mixes}


def submit_compensation(conn: sqlite3.Connection, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    role = row(conn, "SELECT id FROM role_families WHERE slug = ?", (payload.get("role"),))
    level = row(conn, "SELECT id FROM levels WHERE code = ?", (payload.get("level"),))
    location = row(conn, "SELECT id FROM locations WHERE slug = ?", (payload.get("location"),))
    if not role or not level or not location:
        raise ValueError("Role, level, and location are required.")

    cur = conn.execute(
        """
        INSERT INTO submissions(
          user_id, role_family_id, level_id, location_id, company_name,
          base_salary, bonus, equity_annual_value, currency, notes, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            user_id,
            role["id"],
            level["id"],
            location["id"],
            str(payload.get("companyName", "")).strip() or "Undisclosed",
            int(payload.get("baseSalary", 0)),
            int(payload.get("bonus", 0)),
            int(payload.get("equityAnnualValue", 0)),
            payload.get("currency", "USD"),
            payload.get("notes", ""),
            now_iso(),
        ),
    )
    return {"id": cur.lastrowid, "status": "pending"}


def submissions_for_user(conn: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    return rows(
        conn,
        """
        SELECT s.id, s.company_name, s.base_salary, s.bonus, s.equity_annual_value,
               s.currency, s.status, s.created_at, rf.name role_name, l.code level_code,
               loc.name location_name
        FROM submissions s
        JOIN role_families rf ON rf.id = s.role_family_id
        JOIN levels l ON l.id = s.level_id
        JOIN locations loc ON loc.id = s.location_id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC
        """,
        (user_id,),
    )
