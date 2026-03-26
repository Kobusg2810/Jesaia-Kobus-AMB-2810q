import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Final Alignment Tool", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool (V8)")
st.write("Optimized for KT detection and direct Copy/Paste.")

# --- CORE FUNCTIONS ---
def normalize_code(text):
    """Standardizes codes to KM-01-KT01 format for reliable matching"""
    if not text: return ""
    # Remove all spaces/dots/dashes and re-insert standard dashes
    clean = re.sub(r'[^A-Z0-9]', '', text.upper())
    if "KT" in clean:
        # Format KM01KT01 -> KM-01-KT01
        return f"{clean[:2]}-{clean[2:4]}-{clean[4:6]}-{clean[6:]}" if len(clean) > 8 else clean
    return clean

def get_condensed_pages(page_list, mode):
    if not page_list: return "-"
    pages = sorted(list(set([int(p) for p in page_list])))
    if not pages: return "-"
    if mode == "Starting Page Only": return str(pages[0])
    if mode == "Show All": return ", ".join(map(str, pages))
    
    # Condensed (4-6, 12)
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
    st.header("1. Audit Requirements")
    page_mode = st.radio("Page Numbering:", ["Condensed (4-6, 12)", "Show All", "Starting Page Only"])
    st.header("2. Search Precision")
    skip_toc_guide = st.number_input("Skip X pages in Guide (TOC/Covers)", value=0)
    st.info("Tip: If you see topics appearing on page 1-3 incorrectly, increase this number.")

# --- UPLOAD ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("Upload QCTO Curriculum", type="pdf")
with col2:
    guide_files = st.file_uploader("Upload Learner/Facilitator Guides", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 GENERATE ALIGNMENT MATRIX"):
        
        # 1. SCAN CURRICULUM (Priority on KT)
        st.info("Scanning Curriculum for KM and KT codes...")
        # Regex looks for the longest pattern (KM-01-KT01) first, then KM-01
        regex_pattern = r"(KM-\d{2}-KT\d{2}|KM\d{2}KT\d{2}|KM-\d{2}|KM\d{2})"
        
        curriculum_list = []
        with pdfplumber.open(curr_file) as pdf:
            # We skip the first 2 pages of Curriculum often to avoid the general TOC
            for page in pdf.pages[1:]: 
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        matches = re.findall(regex_pattern, line, re.IGNORECASE)
                        for m in matches:
                            clean = m.strip().upper().replace(" ", "")
                            title = line.replace(m, "").strip(": -–—.")
                            curriculum_list.append({"Code": clean, "Title": title[:100]})

        df_curr = pd.DataFrame(curriculum_list).drop_duplicates(subset=['Code'])
        # Sort so KT follows KM
        df_curr = df_curr.sort_values(by="Code", ascending=True)

        if df_curr.empty:
            st.error("No codes found. Is the Curriculum PDF searchable text?")
        else:
            st.success(f"Found {len(df_curr)} KM/KT Topics.")

            # 2. SCAN GUIDES
            raw_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    # Physical page count start
                    for i, page in enumerate(pdf.pages):
                        current_p = i + 1
                        if current_p <= skip_toc_guide: continue
                        
                        text = page.extract_text()
                        if text:
                            # Standardize text for searching
                            text_to_search = text.upper().replace(" ", "")
                            for _, row in df_curr.iterrows():
                                search_code = row['Code'].replace("-", "")
                                if search_code in text_to_search:
                                    raw_hits.append({
                                        "Code": row['Code'],
                                        "Doc": guide.name,
                                        "Page": current_p
                                    })

            # 3. OUTPUT TABLE
            matrix_data = []
            for _, topic in df_curr.iterrows():
                entry = {"Code": topic['Code'], "Description": topic['Title']}
                for doc in guide_files:
                    pages = [h['Page'] for h in raw_hits if h['Code'] == topic['Code'] and h['Doc'] == doc.name]
                    entry[doc.name] = get_condensed_pages(pages, page_mode)
                matrix_data.append(entry)

            final_df = pd.DataFrame(matrix_data)
            
            st.subheader("Final Alignment Matrix")
            st.write("💡 *You can now highlight and copy the table below directly.*")
            # Using st.table for direct copy-paste support
            st.table(final_df)

            # Excel Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 Download Excel Version", output.getvalue(), "QCTO_Alignment.xlsx")
else:st.info("Awaiting documents...")
