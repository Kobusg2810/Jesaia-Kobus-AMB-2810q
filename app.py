import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Alignment Tool V9", layout="wide")

st.title("📑 QCTO Alignment Tool (V9)")
st.write("Fixed: Sub-topic (KT) detection and Page Number formatting.")

# --- CORE FUNCTIONS ---
def get_condensed_pages(page_list, mode):
    """Returns a clean string of page numbers, preventing bullet points."""
    if not page_list: return "-"
    pages = sorted(list(set([int(p) for p in page_list])))
    
    if mode == "Starting Page Only":
        return str(pages[0])
    
    if mode == "Show All":
        return ", ".join(map(str, pages))
    
    # Condensed Logic (e.g., 4-6, 12)
    ranges = []
    if not pages: return "-"
    start = pages[0]
    for i in range(1, len(pages)):
        if pages[i] != pages[i-1] + 1:
            ranges.append(f"{start}-{pages[i-1]}" if start != pages[i-1] else f"{start}")
            start = pages[i]
    ranges.append(f"{start}-{pages[-1]}" if start != pages[-1] else f"{start}")
    return str(", ".join(ranges)) # Force string return

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Display Settings")
    page_mode = st.radio("Page Format:", ["Condensed (4-6, 12)", "Show All", "Starting Page Only"])
    st.header("2. Accuracy Settings")
    skip_pages = st.number_input("Skip first X pages of Guide", value=0)
    st.info("Increase this if topics appear on the Cover/TOC incorrectly.")

# --- UPLOAD ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("Upload QCTO Curriculum", type="pdf")
with col2:
    guide_files = st.file_uploader("Upload Guides (LG/FG)", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 GENERATE ALIGNMENT MATRIX"):
        
        # 1. SCAN CURRICULUM (Smart KT Detection)
        st.info("Step 1: Extracting KMs and KTs from Curriculum...")
        
        # This regex looks for KM and KT even if they are just 'KM 1' or 'KT 1'
        km_pattern = r"KM\s*[-]?\s*(\d{2})"
        kt_pattern = r"KT\s*[-]?\s*(\d{2})"
        
        curriculum_data = []
        current_km = "01" # Default starting KM
        
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        # Detect KM change
                        km_match = re.search(km_pattern, line, re.IGNORECASE)
                        if km_match:
                            current_km = km_match.group(1)
                            full_km_code = f"KM-{current_km}"
                            title = line.replace(km_match.group(0), "").strip(": -–—.")
                            curriculum_data.append({"Code": full_km_code, "Title": title[:100]})
                        
                        # Detect KT
                        kt_match = re.search(kt_pattern, line, re.IGNORECASE)
                        if kt_match:
                            kt_num = kt_match.group(1)
                            full_kt_code = f"KM-{current_km}-KT-{kt_num}"
                            title = line.replace(kt_match.group(0), "").strip(": -–—.")
                            curriculum_data.append({"Code": full_kt_code, "Title": title[:100]})

        df_curr = pd.DataFrame(curriculum_data).drop_duplicates(subset=['Code'])

        if df_curr.empty:
            st.error("No topics found. Please ensure the Curriculum PDF contains searchable text.")
        else:
            st.success(f"Successfully identified {len(df_curr)} Topics (KMs & KTs). Scanning guides...")

            # 2. SCAN GUIDES
            raw_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages):
                        page_num = i + 1
                        if page_num <= skip_pages: continue
                        
                        text = page.extract_text()
                        if text:
                            search_text = text.upper().replace(" ", "").replace("-", "")
                            for _, row in df_curr.iterrows():
                                # Create a 'fuzzy' version of the code to find in guide
                                # e.g. KM-01-KT-01 becomes KM01KT01
                                search_key = row['Code'].replace("-", "")
                                if search_key in search_text:
                                    raw_hits.append({"Code": row['Code'], "Doc": guide.name, "Page": page_num})

            # 3. BUILD THE TABLE
            final_rows = []
            for _, topic in df_curr.iterrows():
                entry = {"KM/KT Code": topic['Code'], "Topic Description": topic['Title']}
                for doc in guide_files:
                    # Collect pages
                    found_pages = [h['Page'] for h in raw_hits if h['Code'] == topic['Code'] and h['Doc'] == doc.name]
                    # Format as clean string (prevents bullet points)
                    entry[doc.name] = str(get_condensed_pages(found_pages, page_mode))
                final_rows.append(entry)

            final_df = pd.DataFrame(final_rows)

            # Display as a clean, copyable table
            st.subheader("Final QCTO Alignment Matrix")
            st.markdown("Highlight the table below to copy/paste into Word.")
            st.table(final_df)

            # Excel Download
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 Download Excel Version", output.getvalue(), "QCTO_Alignment.xlsx")
else:
    st.info("Awaiting Documents...")
