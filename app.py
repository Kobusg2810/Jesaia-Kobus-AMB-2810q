import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Auditor-Ready Aligner", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool")
st.write("Fixed: Data Processing Error & High-Resolution Scan.")

# --- SIDEBAR: AUDIT SETTINGS ---
with st.sidebar:
    st.header("Audit Requirements")
    page_mode = st.radio(
        "Page Numbering Style:",
        ["Show All Pages", "Condensed (e.g. 4-6, 12)", "Starting Page Only"],
        index=1
    )
    st.markdown("---")
    st.header("Scan Precision")
    skip_toc = st.number_input("Ignore first X pages of Guide", value=0)
    use_margins = st.checkbox("Exclude Headers/Footers", value=False)

def format_pages(series):
    """Safe handling of page number lists to prevent ValueErrors"""
    if series.empty:
        return ""
    
    # Convert series to a unique, sorted list of integers
    pages = sorted(list(set(series.dropna().astype(int).tolist())))
    
    if not pages:
        return ""
    
    if page_mode == "Starting Page Only":
        return str(pages[0])
    
    if page_mode == "Show All Pages":
        return ", ".join(map(str, pages))
    
    # Condensed Logic (Standard Audit Format)
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
        st.info("Step 1: Extracting all Modules/Topics from Curriculum...")
        # regex looks for KM-01 or KM-01-KT01 or KM01-KT01
        regex_pattern = r"(KM\s?[-]?\s?\d{2}(?:\s?[-]?\s?KT\s?\d{2})?)"
        
        detected_items = []
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        match = re.search(regex_pattern, line)
                        if match:
                            raw_code = match.group(0)
                            # Clean code to standard format: KM-01-KT01
                            clean_code = re.sub(r'\s+', '', raw_code)
                            if "-" not in clean_code: # Add dashes if missing
                                clean_code = clean_code[:2] + "-" + clean_code[2:]
                            
                            title = line.replace(raw_code, "").strip(": -–—")
                            detected_items.append({"Code": clean_code, "Title": title[:100]})

        df_topics = pd.DataFrame(detected_items).drop_duplicates(subset=['Code'])
        
        if df_topics.empty:
            st.error("No KM/KT codes detected in Curriculum. Check if the PDF is searchable.")
        else:
            st.success(f"Identified {len(df_topics)} unique topics in Curriculum.")
            with st.expander("List of topics found in Curriculum (Verify this list)"):
                st.table(df_topics)

            # --- 2. SCAN GUIDES ---
            st.info("Step 2: Searching your Guides for these topics...")
            results = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for page in pdf.pages:
                        p_num = page.page_number
                        if p_num <= skip_toc: continue
                        
                        # Margin cropping
                        if use_margins:
                            h, w = float(page.height), float(page.width)
                            page_obj = page.crop((0, h*0.1, w, h*0.9))
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        if text:
                            # Standardize text for searching (remove spaces in codes)
                            # This helps find "KM - 01" even if we search for "KM-01"
                            clean_text = re.sub(r'(KM|KT)\s*-\s*', r'\1-', text)
                            
                            for _, row in df_topics.iterrows():
                                code = row['Code']
                                if code in clean_text:
                                    results.append({
                                        "Code": code,
                                        "Topic Title": row['Title'],
                                        "Document": guide.name,
                                        "Page": p_num
                                    })

            # --- 3. GENERATE MATRIX ---
            if not results:
                st.warning("No matches found in your guides. Ensure the KM/KT codes are physically typed in your Learner Guide.")
            else:
                df_results = pd.DataFrame(results)
                
                # Apply the safe format_pages function
                matrix = df_results.groupby(['Code', 'Topic Title', 'Document'])['Page'].apply(format_pages).unstack().reset_index()
                matrix = matrix.fillna("NOT FOUND")
                
                st.subheader("Final QCTO Alignment Matrix")
                st.dataframe(matrix, use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='QCTO_Alignment')
                
                st.download_button(
                    label="📥 Download Excel Matrix",
                    data=output.getvalue(),
                    file_name="QCTO_Alignment_Matrix.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
