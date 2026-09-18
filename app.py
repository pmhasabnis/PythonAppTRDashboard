
import io
import re
import pandas as pd
import pdfplumber
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="SGBAU TR Analytics", page_icon="📊", layout="wide")

# -----------------------------
# SGBAU reference dictionaries
# -----------------------------
GRADE_POINTS = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0}

SUBJECT_NAMES = {
    "1AL100BS": "Applied Mathematics - I",
    "1AL101BS": "Engineering Physics",
    "1AL102ES": "Computer Programming",
    "1AL103ES": "Engineering Mechanics",
    "1AL104BS": "Engineering Physics Lab",
    "1AL105ES": "Computer Programming Lab",
    "1AL106ES": "Engineering Mechanics Lab",
    "1AL107ES": "Workshop Lab",
    "1AL108VS1": "Surveying Skills Lab",
    "1AL108VS7": "Introduction to Web Technology",
    "1AL108VS8": "Electrical Workshop",
    "1AL109AE": "Professional Communication",
    "1AL110CC": "Co-curricular Course",
    "2AL111BS": "Applied Mathematics - II",
    "2AL112BS": "Engineering Chemistry",
    "2AL113ES": "Basic Electrical Engineering",
    "2AL114ES": "Engineering Graphics",
    "2AL115BS": "Engineering Chemistry Lab",
    "2AL116ES": "Basic Electrical Engineering Lab",
    "2AL117ES": "Engineering Graphics Lab",
    "2AL118VS2": "Computer Aided Design & Drafting",
    "2AL118VS3": "Electronic Workshop",
    "2AL118VS5": "Computer Hardware & Networking",
    "2AL119PC2": "Elements of Mechanical Engineering",
    "2AL119PC3": "Introduction to Digital Electronics",
    "2AL119PC4": "Introduction to Digital Electronics / CSE-IT elective",
    "2AL120IK": "Indian Traditional Knowledge",
    "2AL121CC": "Co-curricular Course (CC)",
}

# Codes can vary by branch. Keep explicit mappings based on the supplied TR terminology.
BRANCH_PATTERNS = [
    (r"1AL108VS1", "CE"),
    (r"1AL108VS8", "EE"),
    (r"1AL108VS2|2AL118VS2|2AL119PC2", "ME"),
    (r"1AL108VS3|2AL118VS3|2AL119PC3", "EXTC/ETC"),
    (r"1AL108VS5|2AL118VS5", "IT"),
    (r"1AL108VS7", "CSE/CS"),
    (r"1AL108VS9", "ET"),
    (r"1AL108VS6", "AI&DS"),
    (r"2AL119PC4", "CSE/IT"),
]

ENROLL_RE = re.compile(r"\b\d{2}[A-Z]{2}\d{6}\b")
SUBJECT_RE = re.compile(r"\b\d[A-Z]{2}\d{3}[A-Z]{2}\d?\b")
GRADE_RE = re.compile(r"\b(?:O|A\+|A|B\+|B|C|P|F)\b")
RESULT_RE = re.compile(r"\b(\d{2,3})\s+(PASS|FAIL)\b", re.I)
SGPA_RE = re.compile(r"SGPA\s*-\s*([0-9]+(?:\.[0-9]+)?)", re.I)
PREV_RE = re.compile(r"Previous Sem Marks\s*-\s*([0-9]+)\s*/\s*([0-9]+)\s+([0-9.]+)\s*/\s*([0-9.]+)", re.I)

def clean(s):
    return re.sub(r"\s+", " ", str(s)).strip()

def infer_branch(text):
    found = []
    for pat, branch in BRANCH_PATTERNS:
        if re.search(pat, text):
            found.append(branch)
    return " / ".join(dict.fromkeys(found)) if found else "Not Inferred"

def parse_subject(code, chunk):
    # Extract the grade closest to the subject record.
    grades = GRADE_RE.findall(chunk)
    grade = grades[-1] if grades else ""
    before = chunk.rsplit(grade, 1)[0] if grade else chunk

    # Remove common TR markers before extracting numerical marks.
    before = re.sub(r"XM\.[FI]|ORG-INC|REM-INC|W/[A-Z]", " ", before)
    nums = [int(x) for x in re.findall(r"\b\d{1,3}\b", before)]
    nums = [x for x in nums if x <= 100]

    gp = GRADE_POINTS.get(grade, "")
    if nums and nums[-1] <= 10:
        gp = nums[-1]
        nums = nums[:-1]

    ext = nums[-2] if len(nums) >= 2 else (nums[-1] if nums else "")
    internal = nums[-1] if len(nums) >= 2 else ""
    total = ext + internal if ext != "" and internal != "" else ext

    return ext, internal, total, gp, grade

def extract_student(block, page_no):
    em = ENROLL_RE.search(block)
    if not em:
        return None

    enrollment = em.group()
    first_subject = SUBJECT_RE.search(block)
    if not first_subject:
        return None

    name = clean(block[em.end():first_subject.start()])
    name = re.sub(r"^(?:[-:]\s*)+", "", name)

    result_m = RESULT_RE.search(block)
    sgpa_m = SGPA_RE.search(block)
    prev_m = PREV_RE.search(block)

    rec = {
        "Enrollment No": enrollment,
        "Name of Candidate": name,
        "Marks Obtained": int(result_m.group(1)) if result_m else None,
        "Out Of": 750,
        "Result": result_m.group(2).upper() if result_m else "",
        "SGPA": float(sgpa_m.group(1)) if sgpa_m else None,
        "Previous Sem Marks": int(prev_m.group(1)) if prev_m else None,
        "Previous Sem Out Of": int(prev_m.group(2)) if prev_m else None,
        "Previous Sem SGPA": float(prev_m.group(3)) if prev_m else None,
        "Branch (Inferred)": infer_branch(block),
        "Source Page": page_no,
    }

    codes = list(SUBJECT_RE.finditer(block))
    for i, m in enumerate(codes):
        code = m.group()
        end = codes[i + 1].start() if i + 1 < len(codes) else len(block)
        chunk = block[m.end():end]
        ext, internal, total, gp, grade = parse_subject(code, chunk)
        name2 = SUBJECT_NAMES.get(code, code)
        rec[f"{code} | {name2} | Ext"] = ext
        rec[f"{code} | {name2} | Int"] = internal
        rec[f"{code} | {name2} | Total"] = total
        rec[f"{code} | {name2} | GP"] = gp
        rec[f"{code} | {name2} | Grade"] = grade

    grade_cols = [c for c in rec if c.endswith("| Grade")]
    rec["Backlog Count"] = sum(str(rec[c]).upper() == "F" for c in grade_cols)
    rec["Pass Flag"] = int(rec["Result"] == "PASS")
    return rec

def parse_pdf(data):
    records = []
    pages = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            matches = list(ENROLL_RE.finditer(text))
            for i, m in enumerate(matches):
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                block = text[m.start():end]
                for marker in ["MEANING Of */**/+/@ IS AS UNDER", "TABULATION REGISTER CHECKED"]:
                    p = block.find(marker)
                    if p >= 0:
                        block = block[:p]
                rec = extract_student(block, page.page_number)
                if rec:
                    records.append(rec)

    if not records:
        raise ValueError("No student records detected. The PDF may be scanned/image-only or use a different TR layout.")

    df = pd.DataFrame(records)
    df = df.drop_duplicates("Enrollment No", keep="first").reset_index(drop=True)

    # Normalize numeric columns.
    for c in ["Marks Obtained", "Out Of", "SGPA", "Previous Sem Marks", "Previous Sem Out Of", "Previous Sem SGPA", "Backlog Count", "Pass Flag"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, pages

def make_excel(df):
    bio = io.BytesIO()
    subject_rows = []
    seen = set()
    for c in df.columns:
        m = re.match(r"(.+?) \| (.+?) \| (Ext|Int|Total|GP|Grade)$", c)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            subject_rows.append({"Subject Code": m.group(1), "Subject Name": m.group(2)})

    summary = pd.DataFrame({
        "Metric": ["Students", "Passed", "Failed", "Pass %", "Average SGPA", "Average Marks"],
        "Value": [
            len(df),
            int((df["Result"] == "PASS").sum()),
            int((df["Result"] == "FAIL").sum()),
            round((df["Result"] == "PASS").mean()*100, 2),
            round(pd.to_numeric(df["SGPA"], errors="coerce").mean(), 2),
            round(pd.to_numeric(df["Marks Obtained"], errors="coerce").mean(), 2),
        ]
    })

    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Student Data", index=False)
        pd.DataFrame(subject_rows).to_excel(writer, sheet_name="Subject Legend", index=False)
        summary.to_excel(writer, sheet_name="Summary", index=False)
    return bio.getvalue()

def kpi(title, value, help_text=""):
    st.metric(title, value, help=help_text)

def executive(df):
    st.header("🏛️ Executive Dashboard")
    total = len(df)
    passed = int((df["Result"] == "PASS").sum())
    failed = int((df["Result"] == "FAIL").sum())
    pass_pct = passed/total*100 if total else 0
    avg_sgpa = pd.to_numeric(df["SGPA"], errors="coerce").mean()
    avg_marks = pd.to_numeric(df["Marks Obtained"], errors="coerce").mean()

    a,b,c,d,e = st.columns(5)
    with a: kpi("Total Students", f"{total:,}")
    with b: kpi("Passed", f"{passed:,}")
    with c: kpi("Failed", f"{failed:,}")
    with d: kpi("Pass %", f"{pass_pct:.2f}%")
    with e: kpi("Average SGPA", f"{avg_sgpa:.2f}" if pd.notna(avg_sgpa) else "—")

    st.divider()
    l,r = st.columns(2)
    with l:
        rc = df["Result"].value_counts().rename_axis("Result").reset_index(name="Students")
        st.plotly_chart(px.pie(rc, names="Result", values="Students", hole=.5, title="Overall Result Distribution"), use_container_width=True)
    with r:
        s = pd.to_numeric(df["SGPA"], errors="coerce").dropna()
        st.plotly_chart(px.histogram(s, nbins=20, title="SGPA Distribution", labels={"value":"SGPA"}), use_container_width=True)

    l,r = st.columns(2)
    with l:
        bc = df.groupby("Branch (Inferred)", dropna=False).agg(Students=("Enrollment No","count"), Passed=("Pass Flag","sum")).reset_index()
        bc["Pass %"] = bc["Passed"]/bc["Students"]*100
        st.plotly_chart(px.bar(bc, x="Branch (Inferred)", y="Pass %", text="Pass %", title="Branch-wise Pass Percentage"), use_container_width=True)
    with r:
        bl = df["Backlog Count"].fillna(0).astype(int).value_counts().sort_index().reset_index()
        bl.columns = ["Backlogs","Students"]
        st.plotly_chart(px.bar(bl, x="Backlogs", y="Students", text="Students", title="Backlog Distribution"), use_container_width=True)

    st.subheader("Executive Insights")
    top = df[pd.to_numeric(df["SGPA"], errors="coerce").notna()].nlargest(10, "SGPA")
    weak = df[df["Result"]=="FAIL"].copy()
    insights = [
        f"Overall pass percentage is **{pass_pct:.2f}%**.",
        f"Average SGPA is **{avg_sgpa:.2f}**." if pd.notna(avg_sgpa) else "SGPA was not available for all records.",
        f"**{len(weak):,}** students are marked FAIL in the extracted data.",
        f"The highest SGPA in the extracted data is **{top['SGPA'].max():.2f}**." if len(top) else "Top SGPA could not be calculated.",
    ]
    for x in insights: st.write("•", x)

def department(df):
    st.header("🏢 Department Dashboard")
    branches = sorted(df["Branch (Inferred)"].dropna().astype(str).unique())
    selected = st.multiselect("Select Department / Branch", branches, default=branches)
    x = df[df["Branch (Inferred)"].astype(str).isin(selected)].copy()

    if x.empty:
        st.warning("No records match the selected departments.")
        return

    agg = x.groupby("Branch (Inferred)").agg(
        Students=("Enrollment No","count"),
        Passed=("Pass Flag","sum"),
        Avg_SGPA=("SGPA","mean"),
        Avg_Marks=("Marks Obtained","mean"),
    ).reset_index()
    agg["Pass %"] = agg["Passed"]/agg["Students"]*100

    st.dataframe(agg.round(2), use_container_width=True, hide_index=True)

    l,r = st.columns(2)
    with l:
        st.plotly_chart(px.bar(agg, x="Branch (Inferred)", y="Pass %", text="Pass %", title="Department-wise Pass %"), use_container_width=True)
    with r:
        st.plotly_chart(px.bar(agg, x="Branch (Inferred)", y="Avg_SGPA", text="Avg_SGPA", title="Department-wise Average SGPA"), use_container_width=True)

    # Subject-wise analysis from grade columns.
    grade_cols = [c for c in x.columns if c.endswith("| Grade")]
    rows = []
    for c in grade_cols:
        vals = x[c].astype(str).str.upper()
        appeared = vals.ne("").sum()
        passed = vals.isin(["O","A+","A","B+","B","C","P"]).sum()
        failed = vals.eq("F").sum()
        rows.append({"Subject": c.split("|",2)[1].strip(), "Code": c.split("|",2)[0].strip(),
                     "Appeared": appeared, "Passed": passed, "Failed": failed,
                     "Pass %": passed/appeared*100 if appeared else 0})
    subj = pd.DataFrame(rows).sort_values("Pass %")
    st.subheader("Subject-wise Performance")
    if not subj.empty:
        st.plotly_chart(px.bar(subj, x="Subject", y="Pass %", color="Pass %", title="Subject-wise Pass %", hover_data=["Code","Appeared","Failed"]), use_container_width=True)
        st.dataframe(subj.round(2), use_container_width=True, hide_index=True)

def student_analytics(df):
    st.header("🎓 Student & Student Analytics")
    names = df["Name of Candidate"].astype(str)
    search = st.text_input("Search by Enrollment No. or Student Name")
    x = df.copy()
    if search:
        mask = x["Enrollment No"].astype(str).str.contains(search, case=False, na=False) | names.str.contains(search, case=False, na=False)
        x = x[mask]

    if x.empty:
        st.warning("No student found.")
        return

    student = st.selectbox("Select Student", x["Enrollment No"].astype(str).tolist())
    row = x[x["Enrollment No"].astype(str) == student].iloc[0]

    a,b,c,d,e = st.columns(5)
    with a: kpi("Student", str(row["Name of Candidate"]))
    with b: kpi("Result", str(row["Result"]))
    with c: kpi("Marks", str(row["Marks Obtained"]))
    with d: kpi("SGPA", f"{float(row['SGPA']):.2f}" if pd.notna(row["SGPA"]) else "—")
    with e: kpi("Backlogs", str(int(row["Backlog Count"]) if pd.notna(row["Backlog Count"]) else 0))

    st.write(f"**Enrollment:** {row['Enrollment No']}  |  **Branch:** {row['Branch (Inferred)']}  |  **Previous SGPA:** {row['Previous Sem SGPA']}")

    grade_cols = [c for c in df.columns if c.endswith("| Grade")]
    subject_rows = []
    for c in grade_cols:
        prefix = c.rsplit("| Grade",1)[0]
        total_col = prefix + "| Total"
        gp_col = prefix + "| GP"
        grade = str(row[c])
        subject_rows.append({
            "Subject Code": prefix.split("|")[0].strip(),
            "Subject": prefix.split("|")[1].strip(),
            "Total Marks": row[total_col] if total_col in row.index else "",
            "GP": row[gp_col] if gp_col in row.index else "",
            "Grade": grade,
            "Status": "FAIL" if grade.upper()=="F" else "PASS" if grade else ""
        })
    sd = pd.DataFrame(subject_rows)
    st.subheader("Subject-wise Student Performance")
    st.dataframe(sd, use_container_width=True, hide_index=True)

    valid = sd[sd["GP"].astype(str).str.match(r"^\d+(\.\d+)?$")]
    if not valid.empty:
        st.plotly_chart(px.bar(valid, x="Subject", y="GP", text="Grade", title="Student Grade Point by Subject"), use_container_width=True)

    st.subheader("Peer / Cohort Comparison")
    all_sgpa = pd.to_numeric(df["SGPA"], errors="coerce")
    sgpa = float(row["SGPA"]) if pd.notna(row["SGPA"]) else None
    if sgpa is not None:
        percentile = (all_sgpa <= sgpa).mean()*100
        avg = all_sgpa.mean()
        st.write(f"This student's SGPA is **{sgpa:.2f}** vs cohort average **{avg:.2f}**; approximate cohort percentile: **{percentile:.1f}th**.")

def main():
    st.title("SGBAU Result Tabulation Register Analytics")
    st.caption("PDF → Excel → Executive + Department + Student Analytics")

    with st.sidebar:
        st.header("Input")
        pdf = st.file_uploader("Upload SGBAU TR PDF", type=["pdf"])
        st.info("The converter targets text-based SGBAU TR PDFs similar to the supplied 136-page TR. Scanned PDFs require OCR in a future OCR module.")

    if "df" not in st.session_state:
        st.session_state.df = None

    if pdf and st.button("🚀 Convert TR PDF → Excel", type="primary", use_container_width=True):
        with st.spinner("Extracting student and subject data..."):
            try:
                df, pages = parse_pdf(pdf.getvalue())
                st.session_state.df = df
                st.session_state.pages = pages
                st.success(f"Converted {len(df):,} student records from {pages} PDF pages.")
            except Exception as e:
                st.error(f"Conversion error: {e}")

    df = st.session_state.df
    if df is None:
        st.markdown("""
        ### Complete workflow

        **1. Upload TR PDF**  
        Upload the SGBAU Result Tabulation Register.

        **2. Convert to Excel**  
        The application extracts student-level and subject-level result information.

        **3. Download Excel**  
        The normalized workbook contains Student Data, Subject Legend and Summary sheets.

        **4. Analyze the result**  
        Use the three dashboards:
        - **Executive Dashboard**
        - **Department Dashboard**
        - **Student & Student Analytics**
        """)
        return

    st.download_button(
        "⬇️ Download Converted Excel",
        data=make_excel(df),
        file_name="SGBAU_TR_Converted_Result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    tabs = st.tabs(["🏛️ Executive Dashboard", "🏢 Department Dashboard", "🎓 Student Analytics"])
    with tabs[0]:
        executive(df)
    with tabs[1]:
        department(df)
    with tabs[2]:
        student_analytics(df)

if __name__ == "__main__":
    main()
