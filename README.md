# SQL Server to MySQL Converter

A simple Flask web app that converts common T-SQL syntax into MySQL-compatible SQL.

## Features

- Paste a T-SQL query into the input box
- Convert it to MySQL syntax with a single click
- Review warnings for SQL Server-specific features that may need manual review
- Upload a .sql file
- Keep a short history of recent conversions in the browser

## Local Setup

1. Create and activate a virtual environment:
   - Windows PowerShell:
     - `python -m venv .venv`
     - `.\.venv\Scripts\Activate.ps1`
   - macOS/Linux:
     - `python3 -m venv .venv`
     - `source .venv/bin/activate`

2. Install dependencies:
   - `pip install -r requirements.txt`

3. Run the app:
   - `python app.py`

4. Open the browser at:
   - `http://127.0.0.1:5000`

## Deployment on Render

1. Create a new account at https://render.com/
2. Create a new Web Service and connect this repository
3. Set the build command to:
   - `pip install -r requirements.txt`
4. Set the start command to:
   - `gunicorn app:app`
5. Click Create Web Service

## Notes

This tool focuses on common SQL Server-to-MySQL conversions. Some features such as CLR functions, APPLY, PIVOT, and SQL Server system views may need manual review.
