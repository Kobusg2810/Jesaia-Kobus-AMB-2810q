import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Aligner V10", layout="wide")

st.title("📑 QCTO Alignment Tool (V10)")
st.write("Fixed: No Bullets in Excel | Accurate KT Search | Correct Page Counts")

# --- CORE FUNCTIONS ---
def format_pages_as_string(page_list, mode):
    """Ensures page numbers are a single flat string to prevent bullets in Excel."""
    if not page_list: 
        return "NOT FOUND"
    
    # Get unique, sorted integers
    pages = sorted(list(set([int(p) for p in page_list])))
    
    if mode == "Starting Page Only":
        result = str(pages[0])
    elif mode == "Show All":
        result = ", ".join(map(str, pages))
    else:
        # Condensed (e.g., 4-6, 12)
        ranges = []
        start = pages[0]
        for i in range(1, len(pages)):
            if pages[i] != pages[i-1] + 1:
                ranges.append(f"{start}-{pages[i-1]}" if start != pages[i-1] else f"{start}")
                start = pages[i]
        ranges.append(f"{start}-{pages[-1]}" if start != pages[-1] else f"{start}")
        result = ", ".join(ranges)
    
    # Final safety check: replace any newline characters to prevent Excel from creating bullets
    return str(result).replace('\n', ' ').strip()

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Document Settings")
    page_mode = st.radio("Page Format:", ["Condensed (4-6, 12)", "Show All", "Starting Page Only"])
    skip_pages = st.number_input("Skip first X pages of Guide (TOC/Cover)", value=0, help="Set this to the number of pages in your Table of Contents.")
    
    st.header("2. Search Sensitivity")
    strict_search = st.checkbox("Strict Heading Search", value=False, help="If checked, only finds codes at the start of a paragraph (Skips accidental mentions).")

# --- UPLOAD ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. QCTO Curriculum (Source)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. LG/FG/Assessment (Targets)", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 GENERATE AUDIT-READY MATRIX"):
        
        # 1. SCAN CURRICULUM
        st.info("Step 1: Identifying all Modules and Sub-Topics...")
        
        # Robust pattern for KM and KT
        km_pattern = r"KM\s*[-]?\s*(\d{2})"
        kt_pattern = r"KT\s*[-]?\s*(\d{2})"
        
        curriculum_data = []
        current_km = "01"
        
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        # Find KM
                        km_m = re.search(km_pattern, line, re.IGNORECASE)
                        if km_m:
                            current_km = km_m.group(1)
                            full_code = f"KM-{current_km}"
                            title = line.replace(km_m.group(0), "").strip(": -–—.")
                            curriculum_data.append({"Code": full_code, "Title": title[:100], "Type": "KM"})
                        
                        # Find KT
                        kt_m = re.search(kt_pattern, line, re.IGNORECASE)
                        if kt_m:
                            kt_num = kt_m.group(1)
                            full_code = f"KM-{current_km}-KT-{kt_num}"
                            title = line.replace(kt_m.group(0), "").strip(": -–—.")
                            curriculum_data.append({"Code": full_code, "Title": title[:100], "Type": "KT"})

        df_curr = pd.DataFrame(curriculum_data).drop_duplicates(subset=['Code'])

        if df_curr.empty:
            st.error("No KM/KT topics detected in the Curriculum. Check if the PDF is searchable.")
        else:
            st.success(f"Found {len(df_curr)} Topics. Scanning your guides...")

            # 2. SCAN GUIDES
            raw_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages):
                        phys_page = i + 1
                        if phys_page <= skip_pages: continue
                        
                        text = page.extract_text()
                        if text:
                            # Search line by line for accuracy
                            lines = text.split('\n')
                            for line in lines:
                                line_clean = line.upper().replace(" ", "").replace("-", "")
                                
                                for _, row in df_curr.iterrows():
                                    search_key = row['Code'].replace("-", "")
                                    
                                    # If Strict, the code must be in the first 10 characters of the line
                                    if strict_search:
                                        if search_key in line_clean[:15]:
                                            raw_hits.append({"Code": row['Code'], "Doc": guide.name, "Page": phys_page})
                                    else:
                                        if search_key in line_clean:
                                            raw_hits.append({"Code": row['Code'], "Doc": guide.name, "Page": phys_page})

            # 3. BUILD MATRIX
            final_rows = []
            for _, topic in df_curr.iterrows():
                entry = {
                    "KM/KT Code": topic['Code'],
                    "Description": topic['Title']
                }
                for doc in guide_files:
                    pages_found = [h['Page'] for h in raw_hits if h['Code'] == topic['Code'] and h['Doc'] == doc.name]
                    # Ensure result is a flat string to stop bullets
                    entry[doc.name] = format_pages_as_string(pages_found, page_mode)
                
                final_rows.append(entry)

            final_df = pd.DataFrame(final_rows)

            # 4. DISPLAY & DOWNLOAD
            st.subheader("Final Matrix Preview")
            st.table(final_df) # Static table for easier copy/paste

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Force Excel to treat these columns as text to avoid auto-formatting errors
                final_df.to_excel(writer, index=False, sheet_name='QCTO Alignment')
            
            st.download_button(
                label="📥 Download Excel Matrix",
                data=output.getvalue(),
                file_name="QCTO_Alignment_Matrix_Fixed.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Please upload your Curriculum and Guides.")
