# Simple Expense Tracker (CLI Version)

This is a simple Python command-line application to track expenses, budgets, and reports using SQLite.

## How to Run

python expense_cli.py init
python expense_cli.py add-user --name "Ishan" --email ishan@example.com
python expense_cli.py set-budget --user 1 --category Food --year 2025 --month 12 --amount 200
python expense_cli.py add-expense --user 1 --category Food --amount 50 --note "snack"
python expense_cli.py report-total --user 1 --year 2025 --month 12
