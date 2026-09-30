"""Deterministic fake issuer registers + cross-check."""
import difflib
import random
import re

from . import store

RGPV, MPBSE, ITD, UIDAI, CBSE = "RGPV Bhopal", "MP Board (MPBSE)", "Income Tax Department", "UIDAI", "CBSE"
REGISTERS = {
    RGPV: {"id": "rgpv_results", "key": "roll_no", "fields": ["roll_no", "name", "cgpa", "year", "course"]},
    MPBSE: {"id": "mpbse_results", "key": "roll_no", "fields": ["roll_no", "name", "percentage", "year"]},
    ITD: {"id": "pan_registry", "key": "pan", "fields": ["pan", "name", "dob"]},
}
MINOR_FIELDS = {"year", "course", "dob", "pan_format"}  # OCR can garble these; a lone miss goes to an officer

FIRST = ["RAHUL", "PRIYA", "AMIT", "SNEHA", "VIKAS", "POOJA", "ANKIT", "NEHA", "ROHIT", "KAVITA", "SURESH", "ANJALI",
         "DEEPAK", "MEENA", "ARJUN", "RITU", "MANISH", "SHWETA", "GAURAV", "NIDHI"]
LAST = ["SHARMA", "VERMA", "GUPTA", "PATEL", "SINGH", "YADAV", "JAIN", "MISHRA", "TIWARI", "CHOUHAN", "RATHORE", "SONI"]
COURSES = ["B.TECH (COMPUTER SCIENCE)", "B.TECH (CIVIL)", "B.TECH (MECHANICAL)", "B.TECH (ELECTRONICS)", "MCA", "B.PHARM"]
BRANCH = {"B.TECH (COMPUTER SCIENCE)": "CS", "B.TECH (CIVIL)": "CE", "B.TECH (MECHANICAL)": "ME",
          "B.TECH (ELECTRONICS)": "EC", "MCA": "CA", "B.PHARM": "PH"}

# Rows the demo samples are built from (kept fixed so the samples always match).
FIXED_RGPV = [("0101CS191001", "RAHUL SHARMA", 7.2, 2019, "B.TECH (COMPUTER SCIENCE)"),
              ("0101ME201042", "SNEHA PATEL", 8.6, 2023, "B.TECH (MECHANICAL)")]
FIXED_MPBSE = [("MP2020118745", "PRIYA VERMA", 84.6, 2020),
               ("MP2021204311", "ANKIT YADAV", 78.4, 2021)]
FIXED_PAN = [("ABCPS1234K", "AMIT SINGH", "14/08/1995")]


def seed(n: int = 120):
    rnd = random.Random(2026)
    rg = list(FIXED_RGPV)
    while len(rg) < n:
        c = rnd.choice(COURSES)
        yr = rnd.randint(2017, 2024)
        rg.append((f"0101{BRANCH[c]}{yr % 100:02d}{rnd.randint(1000, 1999)}",
                   f"{rnd.choice(FIRST)} {rnd.choice(LAST)}", round(rnd.uniform(5.0, 9.8), 2), yr, c))
    mp = list(FIXED_MPBSE)
    while len(mp) < n:
        yr = rnd.randint(2017, 2024)
        mp.append((f"MP{yr}{rnd.randint(100000, 999999)}", f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                   round(rnd.uniform(35.0, 98.0), 1), yr))
    pan = list(FIXED_PAN)
    while len(pan) < n:
        p = "".join(rnd.choice("ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(3)) + "P" + rnd.choice("ABCDEFGHJKLMNPRSTUVWXYZ")
        pan.append((f"{p}{rnd.randint(1000, 9999)}{rnd.choice('ABCDEFGHJKLMNPRSTUVWXYZ')}",
                    f"{rnd.choice(FIRST)} {rnd.choice(LAST)}",
                    f"{rnd.randint(1, 28):02d}/{rnd.randint(1, 12):02d}/{rnd.randint(1970, 2004)}"))
    with store.LOCK:
        store._conn.executemany("INSERT OR IGNORE INTO rgpv_results VALUES(?,?,?,?,?)", rg)
        store._conn.executemany("INSERT OR IGNORE INTO mpbse_results VALUES(?,?,?,?)", mp)
        store._conn.executemany("INSERT OR IGNORE INTO pan_registry VALUES(?,?,?)", pan)
        store._conn.commit()


def list_registers() -> list[dict]:
    return [{"id": r["id"], "issuer": iss, "fields": r["fields"],
             "records": store.run(f"SELECT COUNT(*) c FROM {r['id']}", fetch="one")["c"]}
            for iss, r in REGISTERS.items()]


def _norm(v) -> str:
    return re.sub(r"[^A-Z0-9./]", "", str(v).upper())


def _same(key: str, doc, reg) -> bool:
    if key == "name":
        a, b = re.sub(r"[^A-Z]", "", str(doc).upper()), re.sub(r"[^A-Z]", "", str(reg).upper())
        return difflib.SequenceMatcher(None, a, b).ratio() >= 0.85  # OCR-tolerant
    if key in ("cgpa", "percentage"):
        try:
            return abs(float(doc) - float(reg)) <= (0.05 if key == "cgpa" else 0.15)
        except ValueError:
            return False
    if key == "course":
        return _norm(doc)[:8] == _norm(reg)[:8]
    return _norm(doc) == _norm(reg)


PAN_RE = re.compile(r"[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]")


def pan_problem(pan: str, name: str | None) -> str | None:
    """Structure check that needs no register: 4th char = holder type, 5th = surname initial (individuals)."""
    if not PAN_RE.fullmatch(pan):
        return "AAAAA9999A with a valid 4th (holder type) letter"
    if pan[3] == "P" and name and name.split():
        initial = re.sub(r"[^A-Z]", "", name.upper().split()[-1])[:1]
        if initial and pan[4] != initial:
            return f"5th letter should be surname initial {initial}"
    return None


def cross_check(fields: dict, digilocker: str) -> dict:
    issuer = fields.get("issuer") or "Unknown"
    out = {"issuer": issuer, "register": None, "status": "no_register",
           "matched_fields": [], "mismatched_fields": [], "digilocker": digilocker}
    reg = REGISTERS.get(issuer)
    if not reg:
        return out
    if issuer == ITD and fields.get("pan") and (bad := pan_problem(fields["pan"], fields.get("name"))):
        out["mismatched_fields"].append({"key": "pan_format", "document": fields["pan"], "register": bad})
        out["status"] = "mismatch"
        out["register"] = reg["id"]
        return out
    out["register"] = reg["id"]
    key = fields.get(reg["key"])
    row = store.run(f"SELECT * FROM {reg['id']} WHERE {reg['key']}=?", (_norm(key),), "one") if key else None
    if not row:
        out["status"] = "not_found"
        return out
    out["matched_fields"].append(reg["key"])
    for k in reg["fields"]:
        if k == reg["key"] or k not in fields:
            continue
        if _same(k, fields[k], row[k]):
            out["matched_fields"].append(k)
            if k == "name":  # OCR drops spaces in uppercase names; the register spelling is canonical once matched
                fields[k] = str(row[k])
        else:
            out["mismatched_fields"].append({"key": k, "document": str(fields[k]), "register": str(row[k])})
    out["status"] = "mismatch" if out["mismatched_fields"] else "match"
    return out
