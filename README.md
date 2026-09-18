# SGBAU TR Analytics — PDF to Excel and 3-Level Dashboard

## What it does
Upload an SGBAU Result Tabulation Register PDF, convert the text-based TR into a normalized Excel workbook, and analyze the extracted data through:

1. Executive Dashboard
2. Department Dashboard
3. Student & Student Analytics

## Executive Dashboard
Includes:
- Total students
- Passed / Failed
- Overall pass %
- Average SGPA
- Result distribution
- SGPA distribution
- Branch-wise pass %
- Backlog distribution
- Executive insights

## Department Dashboard
Includes:
- Department/branch filters
- Student count
- Passed count
- Pass %
- Average SGPA
- Average marks
- Department comparison
- Subject-wise appeared/pass/fail/pass %
- Subject performance visualization

## Student Analytics
Includes:
- Student search
- Student selection
- Result, marks, SGPA and backlog KPIs
- Subject-wise grades and grade points
- Student grade-point chart
- Cohort average comparison
- Approximate SGPA percentile

## Excel output
The downloaded workbook contains:
- `Student Data`
- `Subject Legend`
- `Summary`

## Streamlit Cloud deployment
Upload `app.py` and `requirements.txt` to GitHub and deploy the application using Streamlit Community Cloud.

## Important validation note
The supplied reference TR is a 136-page text-based SGBAU B.E. Semester-II Summer 2026 TR. The extraction logic is based on that format. Before using the generated workbook for official examination reporting, compare extracted enrollment numbers, names, aggregate marks, result, SGPA and subject grades with the source TR.

## OCR
This version intentionally targets text-based PDFs. A future production version can add OCR fallback for scanned TR PDFs.
