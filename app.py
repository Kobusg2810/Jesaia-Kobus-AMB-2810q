import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Auditor-Ready V12", layout="wide")

st.title("📑 QCTO Alignment Tool (V12)")
st.write("Fixed: Page Number Calibration & Deep Search Logic")

# --- CORE FUNCTIONS ---
def clean_for_search(text):
    """Standardizes text to a 'fingerprint' for matching (ignores all symbols/spaces)"""
    if not text: return ""
    return re.sub(r'[^A-Z0-9]', '', text.upper())

def format_page_string(pages, mode):
    if not pages: return "NOT FOUND"
    p = sorted(list(set([int(x) for x in pages])))
    if mode == "Starting Page Only":
        return str(p[0])
    if mode == "Show All":
        return ", ".join(map(str, p))
    # Condensed (4-6, 12)
    ranges = []
    start = p[0]
    for i in range(1, len(p)):
        if p[i] != p[i-1] + 1:
            ranges.append(f"{start}-{p[i-1]}" if start != p[i-1] else f"{start}")
            start = p[i]
    ranges.append(f"{start}-{p[-1]}" if start != p[-1] else f"{start}")
    return ", ".join(ranges)

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Page Number Calibration")
    st.info("Match the tool to your printed page numbers:")
    start_at_phys = st.number_input("Which physical PDF page is printed as 'Page 1'?", min_value=1, value=1)
    
    st.header("2. Formatting")
    page_mode = st.radio("Display Format:", ["Condensed (4-6, 12)", "Show All", "Starting Page Only"])
    
    st.header("3. Search Sensitivity")
    st.info("If the tool misses topics, uncheck 'Ignore Margins'.")
    ignore_margins = st.checkbox("Ignore Headers/Footers", value=True)

# --- UPLOAD ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. QCTO Curriculum (Source)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Learner/Facilitator Guides", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 GENERATE ACCREDITATION MATRIX"):
        
        # 1. SCAN CURRICULUM
        st.info("Analyzing Curriculum structure...")
        # Patterns for KM-01, KM-01-KT01, and KT0101
        patterns = [r"KM\s*[-]?\s*\d{2}\s*[-]?\s*KT\s*[-]?\s*\d{2}", r"KT\s*\d{4}", r"KM\s*[-]?\s*\d{2}"]
        
        curr_topics = []
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                for line in text.split('\n'):
                    for p in patterns:
                        match = re.search(p, line, re.IGNORECASE)
                        if match:
                            raw_code = match.group(0)
                            display_code = re.sub(r'\s+', '', raw_code).upper()
                            # Search Key (e.g., KT0101)
                            search_key = clean_for_search(raw_code)
                            title = line.replace(raw_code, "").strip(": -–—.")
                            curr_topics.append({"Key": search_key, "Code": display_code, "Title": title[:100]})
                            break # Move to next line once matched

        df_curr = pd.DataFrame(curr_topics).drop_duplicates(subset=['Key'])

        if df_curr.empty:
            st.error("No topics found. Please check if your PDF is searchable text.")
        else:
            st.success(f"Identified {len(df_curr)} topics/sub-topics.")
            with st.expander("Verify Identified Topics List"):
                st.table(df_curr[['Code', 'Title']])

            # 2. SCAN GUIDES
            st.info("Scanning Guides for matches...")
            raw_hits = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages):
                        # --- CALIBRATE PAGE NUMBER ---
                        # Physical index i starts at 0. Physical page is i+1.
                        physical_page = i + 1
                        # If physical page is 5 and start_at_phys is 5, printed_page becomes 1.
                        printed_page = physical_page - start_at_phys + 1
                        
                        # Only scan if we are at or after the starting page
                        if printed_page < 1: continue
                        
                        # Margins
                        if ignore_margins:
                            h, w = float(page.height), float(page.width)
                            page_obj = page.crop((0, h*0.1, w, h*0.9))
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        if text:
                            page_fingerprint = clean_for_search(text)
                            for _, row in df_curr.iterrows():
                                if row['Key'] in page_fingerprint:
                                    raw_hits.append({"Key": row['Key'], "Doc": guide.name, "Page": printed_page})

            # 3. BUILD THE OUTPUT
            matrix_data = []
            for _, topic in df_curr.iterrows():
                row = {"Code": topic['Code'], "Topic Description": topic['Title']}
                for g in guide_files:
                    pages = [h['Page'] for h in raw_hits if h['Key'] == topic['Key'] and h['Doc'] == g.name]
                    row[g.name] = format_page_string(pages, page_mode)
                matrix_data.append(row)

            final_df = pd.DataFrame(matrix_data)
            st.subheader("Final QCTO Alignment Matrix")
            st.table(final_df) # HTML table for easy copy-paste

            # Excel Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 Download Excel Matrix", output.getvalue(), "QCTO_Alignment_Final.xlsx")

else:
    st.info("Please upload your documents to begin.")
