from __future__ import annotations

from server.database import connect
from server.security import hash_password, now_iso


ROLE_FAMILIES = [
    ("software-engineering", "Software Engineering", "Engineering"),
    ("product-management", "Product Management", "Product"),
    ("data-science", "Data Science", "Data"),
    ("design", "Product Design", "Design"),
]

LEVELS = [
    ("L3", "Associate", 3, "Executes scoped tasks with guidance"),
    ("L4", "Mid-Level", 4, "Owns well-defined features and decisions"),
    ("L5", "Senior", 5, "Owns ambiguous projects across a team"),
    ("L6", "Staff / Lead", 6, "Sets direction across teams"),
    ("L7", "Principal / Group", 7, "Shapes multi-team strategy"),
]

LOCATIONS = [
    ("sf-bay-area", "San Francisco Bay Area", "US West", 1.28),
    ("new-york", "New York", "US East", 1.18),
    ("seattle", "Seattle", "US West", 1.12),
    ("austin", "Austin", "US Central", 0.96),
    ("remote-us", "Remote US", "Distributed", 1.00),
    ("bengaluru", "Bengaluru", "India", 0.42),
]

COMPANIES = [
    ("Aster Cloud", "public", "5000+"),
    ("Northstar AI", "late-stage", "1001-5000"),
    ("Cobalt Systems", "growth", "501-1000"),
    ("Fjord Analytics", "private", "201-500"),
    ("OrbitPay", "public", "5000+"),
]


def seed() -> None:
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO users(email, name, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("demo@levellens.local", "Demo Analyst", hash_password("demo-password"), "admin", now_iso()),
            )

        for slug, name, discipline in ROLE_FAMILIES:
            conn.execute(
                "INSERT OR IGNORE INTO role_families(slug, name, discipline) VALUES (?, ?, ?)",
                (slug, name, discipline),
            )
        for code, name, rank, scope in LEVELS:
            conn.execute(
                "INSERT OR IGNORE INTO levels(code, name, rank, scope) VALUES (?, ?, ?, ?)",
                (code, name, rank, scope),
            )
        for slug, name, region, multiplier in LOCATIONS:
            conn.execute(
                "INSERT OR IGNORE INTO locations(slug, name, region, market_multiplier) VALUES (?, ?, ?, ?)",
                (slug, name, region, multiplier),
            )
        for name, stage, size_band in COMPANIES:
            conn.execute(
                "INSERT OR IGNORE INTO companies(name, stage, size_band) VALUES (?, ?, ?)",
                (name, stage, size_band),
            )

        if conn.execute("SELECT COUNT(*) FROM compensation_records").fetchone()[0] == 0:
            roles = {r["slug"]: r["id"] for r in conn.execute("SELECT id, slug FROM role_families")}
            levels = {r["code"]: r["id"] for r in conn.execute("SELECT id, code FROM levels")}
            locations = {r["slug"]: (r["id"], r["market_multiplier"]) for r in conn.execute("SELECT id, slug, market_multiplier FROM locations")}
            companies = [r["id"] for r in conn.execute("SELECT id FROM companies ORDER BY id")]
            base_by_role = {
                "software-engineering": 97000,
                "product-management": 103000,
                "data-science": 101000,
                "design": 92000,
            }
            level_factor = {"L3": 1.0, "L4": 1.24, "L5": 1.62, "L6": 2.12, "L7": 2.72}
            for role_slug, base in base_by_role.items():
                for level_code, factor in level_factor.items():
                    for location_slug, (location_id, location_factor) in locations.items():
                        for idx, company_id in enumerate(companies):
                            variance = 0.94 + (idx * 0.035)
                            adjusted = int(base * factor * location_factor * variance)
                            bonus = int(adjusted * (0.08 + (idx % 3) * 0.035))
                            equity = int(adjusted * (0.12 + list(level_factor).index(level_code) * 0.055 + idx * 0.015))
                            conn.execute(
                                """
                                INSERT INTO compensation_records(
                                  role_family_id, level_id, location_id, company_id,
                                  base_salary, bonus, equity_annual_value, currency,
                                  source, confidence_score, effective_date, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'USD', 'seeded-market-model', ?, '2026-01-01', ?)
                                """,
                                (
                                    roles[role_slug],
                                    levels[level_code],
                                    location_id,
                                    company_id,
                                    adjusted,
                                    bonus,
                                    equity,
                                    0.82 + (idx * 0.025),
                                    now_iso(),
                                ),
                            )


if __name__ == "__main__":
    from server.database import migrate

    migrate()
    seed()

