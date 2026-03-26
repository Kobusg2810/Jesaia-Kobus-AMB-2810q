import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Auditor-Ready Aligner", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool")
st.write("V6: High-Precision Scan & Data Stability Fix")

# --- FUNCTIONS ---
def get_condensed_pages(page_list, mode):
    """Accurate page number formatting without Pandas ambiguity"""
    if not page_list:
        return "NOT FOUND"
    
    # Clean and sort unique page numbers
    pages = sorted(list(set([int(p) for p in page_list if p is not None])))
    
    if not pages:
        return "NOT FOUND"
    
    if mode == "Starting Page Only":
        return str(pages[0])
    
    if mode == "Show All Pages":
        return ", ".join(map(str, pages))
    
    # Condensed Logic (Standard Audit Format: 4-6, 12)
    ranges = []
    start = pages[0]
    for i in range(1, len(pages)):
        if pages[i] != pages[i-1] + 1:
            ranges.append(f"{start}-{pages[i-1]}" if start != pages[i-1] else f"{start}")
            start = pages[i]
    ranges.append(f"{start}-{pages[-1]}" if start != pages[-1] else f"{start}")
    return ", ".join(ranges)

# --- SIDEBAR ---
with st.sidebar:
    st.header("Audit Settings")
    page_mode = st.radio(
        "Page Numbering Style:",
        ["Show All Pages", "Condensed (e.g. 4-6, 12)", "Starting Page Only"],
        index=1
    )
    st.markdown("---")
    skip_toc = st.number_input("Ignore first X pages of Guide (TOC)", value=0)
    use_margins = st.checkbox("Strict Scan (Ignore Headers/Footers)", value=False)

# --- MAIN INTERFACE ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. QCTO Curriculum (Source PDF)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Learner/Facilitator Guides (Target PDFs)", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🔍 START HIGH-RESOLUTION ALIGNMENT"):
        
        # 1. SCAN CURRICULUM FOR ALL KM/KT CODES
        st.info("Scanning Curriculum for all required topics...")
        # Broad regex to catch KM-01, KM-01-KT01, KM 01, KM01-KT01 etc.
        regex_pattern = r"(KM\s?[-]?\s?\d{2}(?:\s?[-]?\s?KT\s?\d{2})?)"
        
        curriculum_topics = []
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    for line in content.split('\n'):
                        match = re.search(regex_pattern, line, re.IGNORECASE)
                        if match:
                            raw_code = match.group(0)
                            # Standardize to KM-01-KT01
                            clean_code = re.sub(r'\s+', '', raw_code).upper()
                            if "-" not in clean_code:
                                clean_code = clean_code[:2] + "-" + clean_code[2:]
                            
                            title = line.replace(raw_code, "").strip(": -–—")
                            curriculum_topics.append({"Code": clean_code, "Title": title[:100]})

        df_curr = pd.DataFrame(curriculum_topics).drop_duplicates(subset=['Code'])
        
        if df_curr.empty:
            st.error("No KM or KT codes found in the Curriculum. Please check if the PDF is searchable.")
        else:
            st.success(f"Found {len(df_curr)} Topics/Modules in Curriculum.")
            with st.expander("Verify Identified Topics"):
                st.table(df_curr)

            # 2. SCAN GUIDES
            st.info("Scanning Guides for matches... please wait.")
            raw_hits = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for page in pdf.pages:
                        p_num = page.page_number
                        if p_num <= skip_toc: continue
                        
                        if use_margins:
                            h, w = float(page.height), float(page.width)
                            page_obj = page.crop((0, h*0.1, w, h*0.9))
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        if text:
                            # Clean text to find codes even with weird spacing
                            clean_text = re.sub(r'\s+', '', text).upper()
                            
                            for _, row in df_curr.iterrows():
                                code_to_find = row['Code'].replace("-", "")
                                if code_to_find in clean_text:
                                    raw_hits.append({
                                        "Code": row['Code'],
                                        "Title": row['Title'],
                                        "Doc": guide.name,
                                        "Page": p_num
                                    })

            # 3. BUILD MATRIX WITHOUT PANDAS GROUPBY ERRORS
            if not raw_hits:
                st.warning("No matches found in your guides. Ensure KM/KT codes are typed inside the guides.")
            else:
                # Convert list of hits to a table
                df_results = pd.DataFrame(raw_hits)
                
                # Create the final alignment rows
                matrix_rows = []
                for code in df_curr['Code'].tolist():
                    title = df_curr[df_curr['Code'] == code]['Title'].iloc[0]
                    row_entry = {"KM/KT Code": code, "Topic Description": title}
                    
                    for doc_name in [g.name for g in guide_files]:
                        # Get pages for this specific code and this specific document
                        matching_pages = df_results[(df_results['Code'] == code) & (df_results['Doc'] == doc_name)]['Page'].tolist()
                        row_entry[doc_name] = get_condensed_pages(matching_pages, page_mode)
                    
                    matrix_rows.append(row_entry)

                final_df = pd.DataFrame(matrix_rows)

                st.subheader("Final QCTO Alignment Matrix")
                st.dataframe(final_df, use_container_width=True)

                # Export
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='Alignment')
                
                st.download_button(
                    "📥 Download Excel Matrix",
                    data=output.getvalue(),
                    file_name="QCTO_Alignment_Matrix.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
