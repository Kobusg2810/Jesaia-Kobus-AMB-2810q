import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Alignment Tool Pro", layout="wide")

st.title("📑 Professional QCTO Alignment Tool")
st.markdown("---")

# --- SIDEBAR SETTINGS ---
with st.sidebar:
    st.header("Scanning Precision")
    pages_to_skip = st.number_input("Skip first X pages (Table of Contents)", min_value=0, value=3)
    ignore_margins = st.checkbox("Ignore Headers & Footers", value=True)
    
    st.header("Matrix Formatting")
    page_format = st.selectbox(
        "Page Number Format",
        ["First Mention Only", "Condensed (e.g., 5, 8-10)", "All Mentions"]
    )

def condense_pages(series):
    if series.empty: return ""
    pages = sorted(list(set(series.dropna().astype(int).tolist())))
    if not pages: return ""
    if page_format == "First Mention Only": return str(pages[0])
    if page_format == "All Mentions": return ", ".join(map(str, pages))
    
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
    st.subheader("1. Curriculum (Source)")
    curr_file = st.file_uploader("Upload QCTO Curriculum PDF", type="pdf")
with col2:
    st.subheader("2. Learning Material (Targets)")
    guide_files = st.file_uploader("Upload LG/FG/Assessments", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 Generate Clean Alignment Matrix"):
        
        # 1. SCAN CURRICULUM
        st.write("🔍 Extracting codes from Curriculum...")
        regex_pattern = r"(KM-\d{2}(?:-KT\d{2})?)"
        topics_data = []
        
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    for line in lines:
                        match = re.search(regex_pattern, line)
                        if match:
                            code = match.group(0)
                            title = line.replace(code, "").strip(": -")
                            topics_data.append({"Code": code, "Title": title[:100]})

        unique_topics = []
        seen = set()
        for t in topics_data:
            if t["Code"] not in seen:
                unique_topics.append(t)
                seen.add(t["Code"])
        
        if not unique_topics:
            st.error("No codes found in Curriculum.")
        else:
            st.success(f"Found {len(unique_topics)} topics. Scanning guides (skipping first {pages_to_skip} pages)...")

            # 2. SCAN GUIDES
            all_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    # Skip the Table of Contents pages
                    pages_to_scan = pdf.pages[pages_to_skip:] 
                    
                    for i, page in enumerate(pages_to_scan, pages_to_skip + 1):
                        
                        # --- CROP HEADER/FOOTER ---
                        if ignore_margins:
                            # Only look at the middle 80% of the page
                            height = float(page.height)
                            width = float(page.width)
                            # Crop: (x0, top, x1, bottom)
                            bbox = (0, height * 0.1, width, height * 0.9)
                            page_obj = page.within_bbox(bbox)
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        
                        if text:
                            for item in unique_topics:
                                # Use regex for "Whole Word" matching to avoid partial hits
                                pattern = r"\b" + re.escape(item["Code"]) + r"\b"
                                if re.search(pattern, text):
                                    all_hits.append({
                                        "Code": item["Code"],
                                        "Title": item["Title"],
                                        "Doc": guide.name,
                                        "Page": i
                                    })

            if not all_hits:
                st.warning("No matches found. Try reducing the 'Pages to skip' or unchecking 'Ignore Headers'.")
            else:
                # 3. CONSTRUCT MATRIX
                df_hits = pd.DataFrame(all_hits)
                matrix = df_hits.groupby(['Code', 'Title', 'Doc'])['Page'].apply(condense_pages).unstack().reset_index()
                matrix = matrix.fillna("").sort_values(by="Code")

                st.write("### Cleaned Alignment Matrix")
                st.dataframe(matrix, use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='Alignment')
                
                st.download_button("📥 Download Excel", output.getvalue(), "QCTO_Matrix_Clean.xlsx")

else:
    st.info("Upload documents to begin.")
