import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Master Aligner V11", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool (V11)")
st.write("Specialized for KM/KT Sub-topic Hierarchy (e.g., KT0101)")

# --- FUNCTIONS ---
def clean_text_for_search(text):
    """Standardizes text for matching"""
    if not text: return ""
    return re.sub(r'[^A-Z0-9]', '', text.upper())

def format_page_string(pages, mode):
    """Ensures no bullets or newlines enter Excel"""
    if not pages: return "NOT FOUND"
    p = sorted(list(set([int(x) for x in pages])))
    if mode == "Starting Page Only":
        res = str(p[0])
    elif mode == "Show All":
        res = ", ".join(map(str, p))
    else:
        ranges = []
        start = p[0]
        for i in range(1, len(p)):
            if p[i] != p[i-1] + 1:
                ranges.append(f"{start}-{p[i-1]}" if start != p[i-1] else f"{start}")
                start = p[i]
        ranges.append(f"{start}-{p[-1]}" if start != p[-1] else f"{start}")
        res = ", ".join(ranges)
    return res.replace('\n', ' ').strip()

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Audit Options")
    page_mode = st.radio("Page Format:", ["Condensed (4-6, 12)", "Show All", "Starting Page Only"])
    st.header("2. Scanning Precision")
    skip_toc = st.number_input("Skip first X pages of Guide (TOC)", value=0)
    st.info("If topics appear on pg 1-3 incorrectly, set this to the number of TOC pages.")

# --- MAIN ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. QCTO Curriculum PDF", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Learner/Facilitator Guides", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 GENERATE ACCREDITATION MATRIX"):
        
        # 1. EXTRACT HIERARCHY FROM CURRICULUM
        st.info("Step 1: Building Hierarchy from Curriculum...")
        
        # Regex for KM-01, KM-01-KT01, and KT0101
        patterns = {
            'KM': r"KM\s*[-]?\s*(\d{2})",
            'KT_FULL': r"KM\s*[-]?\s*\d{2}\s*[-]?\s*KT\s*[-]?\s*(\d{2})",
            'KT_SUB': r"KT\s*(\d{4})"
        }
        
        curriculum_map = []
        current_km = "01"
        
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                for line in text.split('\n'):
                    # Check for KM (KM-01)
                    km_m = re.search(patterns['KM'], line, re.IGNORECASE)
                    if km_m:
                        current_km = km_m.group(1)
                        code = f"KM-{current_km}"
                        desc = line.replace(km_m.group(0), "").strip(": -–—.")
                        curriculum_map.append({"Code": code, "Search": "KM"+current_km, "Desc": desc})
                    
                    # Check for KT Full (KM-01-KT01)
                    ktf_m = re.search(patterns['KT_FULL'], line, re.IGNORECASE)
                    if ktf_m:
                        kt_num = ktf_m.group(1)
                        code = f"KM-{current_km}-KT-{kt_num}"
                        desc = line.replace(ktf_m.group(0), "").strip(": -–—.")
                        curriculum_map.append({"Code": code, "Search": "KM"+current_km+"KT"+kt_num, "Desc": desc})
                    
                    # Check for KT Sub (KT0101)
                    kts_m = re.search(patterns['KT_SUB'], line, re.IGNORECASE)
                    if kts_m:
                        sub_num = kts_m.group(1)
                        code = f"KT-{sub_num}"
                        desc = line.replace(kts_m.group(0), "").strip(": -–—.")
                        curriculum_map.append({"Code": code, "Search": "KT"+sub_num, "Desc": desc})

        df_curr = pd.DataFrame(curriculum_map).drop_duplicates(subset=['Code'])
        
        if df_curr.empty:
            st.error("No topics detected. Ensure Curriculum PDF is searchable text.")
        else:
            st.success(f"Identified {len(df_curr)} total topics and sub-topics.")
            with st.expander("Verify Identified Topics"):
                st.table(df_curr[['Code', 'Desc']])

            # 2. SCAN GUIDES
            st.info("Step 2: Searching Guides...")
            all_hits = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages):
                        p_idx = i + 1
                        if p_idx <= skip_toc: continue
                        
                        text = page.extract_text()
                        if text:
                            page_clean = clean_text_for_search(text)
                            for _, row in df_curr.iterrows():
                                if row['Search'] in page_clean:
                                    all_hits.append({"Code": row['Code'], "Doc": guide.name, "Page": p_idx})

            # 3. CONSOLIDATE
            if not all_hits:
                st.warning("No matches found in guides. Ensure codes like 'KT0101' are in the text.")
            else:
                final_data = []
                for _, topic in df_curr.iterrows():
                    row = {"Module/Topic Code": topic['Code'], "Description": topic['Desc']}
                    for g in guide_files:
                        pgs = [h['Page'] for h in all_hits if h['Code'] == topic['Code'] and h['Doc'] == g.name]
                        row[g.name] = format_page_string(pgs, page_mode)
                    final_data.append(row)
                
                final_df = pd.DataFrame(final_data)
                
                st.subheader("Final Alignment Matrix")
                st.table(final_df) # HTML table for copy/paste
                
                # Excel Export
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    final_df.to_excel(writer, index=False)
                st.download_button("📥 Download Excel Matrix", output.getvalue(), "QCTO_Alignment_Final.xlsx")

else:
    st.info("Upload your Curriculum and Learner Guides to begin.")
