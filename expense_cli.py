#!/usr/bin/env python3
"""
Simple Expense Tracker CLI
Usage examples:
  python expense_cli.py init
  python expense_cli.py add-user --name "Ishan" --email ishan@example.com
  python expense_cli.py set-budget --user 1 --category Food --year 2025 --month 12 --amount 200
  python expense_cli.py add-expense --user 1 --category Food --amount 190 --note "dinner"
  python expense_cli.py report-total --user 1 --year 2025 --month 12
  python expense_cli.py report-by-category --user 1 --year 2025 --month 12
"""
import sqlite3
import argparse
from datetime import datetime, date

DB = "expense_simple.db"
DEFAULT_ALERT_PCT = 10.0  # percent

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT
);
"""

CREATE_BUDGETS = """
CREATE TABLE IF NOT EXISTS budgets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  category TEXT NOT NULL,
  year INTEGER NOT NULL,
  month INTEGER NOT NULL,
  amount REAL NOT NULL,
  alert_pct REAL,
  UNIQUE(user_id, category, year, month)
);
"""

CREATE_EXPENSES = """
CREATE TABLE IF NOT EXISTS expenses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  category TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT,
  date TEXT NOT NULL
);
"""


def get_conn():
    return sqlite3.connect(DB)


def init_db(args):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(CREATE_USERS)
        cur.execute(CREATE_BUDGETS)
        cur.execute(CREATE_EXPENSES)
        conn.commit()
    print(f"Initialized database `{DB}` (tables: users, budgets, expenses).")


def add_user(args):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", (args.name, args.email))
        conn.commit()
        uid = cur.lastrowid
    print(f"Created user id={uid}, name={args.name}, email={args.email}")


def set_budget(args):
    with get_conn() as conn:
        cur = conn.cursor()
        # try update first
        cur.execute("""SELECT id FROM budgets WHERE user_id=? AND category=? AND year=? AND month=?""",
                    (args.user, args.category, args.year, args.month))
        row = cur.fetchone()
        if row:
            cur.execute("""UPDATE budgets SET amount=?, alert_pct=? WHERE id=?""",
                        (args.amount, args.alert_pct, row[0]))
            print(f"Updated budget id={row[0]}")
        else:
            cur.execute("""INSERT INTO budgets (user_id, category, year, month, amount, alert_pct)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (args.user, args.category, args.year, args.month, args.amount, args.alert_pct))
            print(f"Inserted budget id={cur.lastrowid}")
        conn.commit()


def add_expense(args):
    d = args.date or date.today().isoformat()
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""INSERT INTO expenses (user_id, category, amount, note, date)
                       VALUES (?, ?, ?, ?, ?)""",
                    (args.user, args.category, args.amount, args.note, d))
        conn.commit()
        eid = cur.lastrowid
        print(f"Added expense id={eid}: user={args.user} category={args.category} amount={args.amount} date={d}")
        # check budget & alert
        year = int(d.split("-")[0])
        month = int(d.split("-")[1])
        cur.execute("""SELECT amount, alert_pct FROM budgets
                       WHERE user_id=? AND category=? AND year=? AND month=?""",
                    (args.user, args.category, year, month))
        b = cur.fetchone()
        if b:
            budget_amount, alert_pct = b[0], (b[1] if b[1] is not None else DEFAULT_ALERT_PCT)
            cur.execute("""SELECT COALESCE(SUM(amount),0) FROM expenses
                           WHERE user_id=? AND category=? AND substr(date,1,4)=? AND substr(date,6,2)=?""",
                        (args.user, args.category, str(year), f"{month:02d}"))
            spent = cur.fetchone()[0] or 0.0
            remaining = max(budget_amount - spent, 0.0)
            remaining_pct = (remaining / budget_amount) * 100 if budget_amount > 0 else 0.0
            if spent > budget_amount:
                print(f"WARNING: Budget exceeded for {args.category} — spent {spent:.2f}, budget {budget_amount:.2f}")
            elif remaining_pct <= alert_pct:
                print(f"ALERT: Low budget remaining for {args.category} — remaining {remaining:.2f} ({remaining_pct:.1f}% left)")
        else:
            print("No budget set for this category/month (no alerts).")


def report_total(args):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT COALESCE(SUM(amount),0) FROM expenses
                       WHERE user_id=? AND substr(date,1,4)=? AND substr(date,6,2)=?""",
                    (args.user, str(args.year), f"{args.month:02d}"))
        total = cur.fetchone()[0] or 0.0
    print(f"Total spending for user {args.user} in {args.year}-{args.month:02d}: {total:.2f}")


def report_by_category(args):
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("""SELECT category, COALESCE(SUM(amount),0) FROM expenses
                       WHERE user_id=? AND substr(date,1,4)=? AND substr(date,6,2)=?
                       GROUP BY category""",
                    (args.user, str(args.year), f"{args.month:02d}"))
        rows = cur.fetchall()
        print(f"Spending by category for user {args.user} in {args.year}-{args.month:02d}:")
        for cat, amt in rows:
            # find budget if any
            cur.execute("""SELECT amount FROM budgets WHERE user_id=? AND category=? AND year=? AND month=?""",
                        (args.user, cat, args.year, args.month))
            b = cur.fetchone()
            b_amt = b[0] if b else None
            print(f"  {cat}: spent {amt:.2f}" + (f", budget {b_amt:.2f}" if b_amt is not None else ""))

        # Also show budgets that had no spending
        cur.execute("""SELECT category, amount FROM budgets
                       WHERE user_id=? AND year=? AND month=?""",
                    (args.user, args.year, args.month))
        budgets = cur.fetchall()
        spent_cats = {r[0] for r in rows}
        for cat, bamt in budgets:
            if cat not in spent_cats:
                print(f"  {cat}: spent 0.00, budget {bamt:.2f}")


def parse_args():
    p = argparse.ArgumentParser(description="Simple Expense Tracker CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=init_db)

    pu = sub.add_parser("add-user")
    pu.add_argument("--name", required=True)
    pu.add_argument("--email", default=None)
    pu.set_defaults(func=add_user)

    pb = sub.add_parser("set-budget")
    pb.add_argument("--user", type=int, required=True)
    pb.add_argument("--category", required=True)
    pb.add_argument("--year", type=int, required=True)
    pb.add_argument("--month", type=int, choices=range(1,13), required=True)
    pb.add_argument("--amount", type=float, required=True)
    pb.add_argument("--alert-pct", type=float, dest="alert_pct", default=None,
                    help="custom alert percentage (e.g., 10 for 10%% left)")
    pb.set_defaults(func=set_budget)

    pe = sub.add_parser("add-expense")
    pe.add_argument("--user", type=int, required=True)
    pe.add_argument("--category", required=True)
    pe.add_argument("--amount", type=float, required=True)
    pe.add_argument("--note", default="")
    pe.add_argument("--date", default=None, help="YYYY-MM-DD (optional; default today)")
    pe.set_defaults(func=add_expense)

    pr1 = sub.add_parser("report-total")
    pr1.add_argument("--user", type=int, required=True)
    pr1.add_argument("--year", type=int, required=True)
    pr1.add_argument("--month", type=int, choices=range(1,13), required=True)
    pr1.set_defaults(func=report_total)

    pr2 = sub.add_parser("report-by-category")
    pr2.add_argument("--user", type=int, required=True)
    pr2.add_argument("--year", type=int, required=True)
    pr2.add_argument("--month", type=int, choices=range(1,13), required=True)
    pr2.set_defaults(func=report_by_category)

    return p.parse_args()


def main():
    args = parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
