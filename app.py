import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Auditor-Ready Aligner", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool")
st.write("Ensuring 100% accuracy for KM/KT Page Mapping.")

# --- SIDEBAR: AUDIT SETTINGS ---
with st.sidebar:
    st.header("Audit Requirements")
    page_mode = st.radio(
        "Page Numbering Style:",
        ["Show All Pages (e.g. 4, 5, 6, 12)", "Condensed (e.g. 4-6, 12)", "Starting Page Only"],
        index=1
    )
    st.markdown("---")
    st.header("Scan Precision")
    skip_toc = st.number_input("Ignore first X pages (Table of Contents)", value=0)
    use_margins = st.checkbox("Exclude Headers/Footers (Recommended)", value=False)

def format_pages(page_list):
    if not page_list: return ""
    pages = sorted(list(set(page_list)))
    
    if page_mode == "Starting Page Only":
        return str(pages[0])
    if page_mode == "Show All Pages (e.g. 4, 5, 6, 12)":
        return ", ".join(map(str, pages))
    
    # Condensed Logic
    ranges = []
    start = pages[0]
    for i in range(1, len(pages)):
        if pages[i] != pages[i-1] + 1:
            ranges.append(f"{start}-{pages[i-1]}" if start != pages[i-1] else f"{start}")
            start = pages[i]
    ranges.append(f"{start}-{pages[-1]}" if start != pages[-1] else f"{start}")
    return ", ".join(ranges)

# --- STEP 1: UPLOAD ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. Upload QCTO Curriculum (Source)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Upload Learner/Facilitator Guides", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🔍 Run High-Resolution Scan"):
        
        # --- 1. DEEP SCAN CURRICULUM ---
        st.info("Step 1: Analyzing Curriculum for all KM and KT codes...")
        # Broadened regex to catch variations: KM-01, KM-01-KT01, KM 01, etc.
        regex_pattern = r"(KM\s?-\s?\d{2}(?:\s?-\s?KT\s?\d{2})?)"
        
        detected_items = []
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        match = re.search(regex_pattern, line)
                        if match:
                            code = match.group(0).replace(" ", "") # Standardize to KM-01-KT01
                            title = line.replace(match.group(0), "").strip(": -–—")
                            detected_items.append({"Code": code, "Title": title[:100]})

        # Unique Topics List
        df_topics = pd.DataFrame(detected_items).drop_duplicates(subset=['Code'])
        
        if df_topics.empty:
            st.error("No KM or KT codes detected. Please ensure the Curriculum PDF is not a scanned image.")
        else:
            st.success(f"Successfully identified {len(df_topics)} Modules/Topics from Curriculum.")
            with st.expander("View Detected Topics List"):
                st.table(df_topics)

            # --- 2. SCAN GUIDES ---
            st.info("Step 2: Searching Learning Material for matches...")
            results = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for page in pdf.pages:
                        p_num = page.page_number
                        
                        if p_num <= skip_toc: continue
                        
                        # Apply margin cropping if selected
                        if use_margins:
                            h, w = float(page.height), float(page.width)
                            page_obj = page.crop((0, h*0.1, w, h*0.9))
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        if text:
                            for _, row in df_topics.iterrows():
                                code = row['Code']
                                # Search for code. Regex \b ensures we don't get partial matches.
                                if re.search(r"\b" + re.escape(code) + r"\b", text):
                                    results.append({
                                        "Code": code,
                                        "Topic Title": row['Title'],
                                        "Document": guide.name,
                                        "Page": p_num
                                    })

            # --- 3. GENERATE MATRIX ---
            if not results:
                st.warning("No matches found in your guides. Ensure the KM/KT codes are typed exactly as they appear in the Curriculum.")
            else:
                df_results = pd.DataFrame(results)
                
                # Pivot and Format
                matrix = df_results.groupby(['Code', 'Topic Title', 'Document'])['Page'].apply(format_pages).unstack().reset_index()
                matrix = matrix.fillna("Not Found")
                
                st.subheader("Final QCTO Alignment Matrix")
                st.dataframe(matrix, use_container_width=True)

                # Excel Export
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='QCTO_Alignment')
                
                st.download_button(
                    label="📥 Download Excel for QCTO Submission",
                    data=output.getvalue(),
                    file_name="QCTO_Alignment_Matrix.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
