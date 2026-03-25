import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Aligner Pro V3", layout="wide")

st.title("📑 Professional QCTO Alignment Tool")
st.write("Fixed: Page Numbering Logic & Accuracy")

# --- SIDEBAR ---
with st.sidebar:
    st.header("Scanning Settings")
    pages_to_skip = st.number_input("Skip first X pages (Covers/TOC)", min_value=0, value=3)
    
    st.header("Precision Settings")
    ignore_margins = st.checkbox("Ignore Headers & Footers", value=True)
    margin_percent = st.slider("Header/Footer size (%)", 5, 25, 10)
    
    st.header("Formatting")
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
    curr_file = st.file_uploader("1. QCTO Curriculum (Source)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Guides (Targets)", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🚀 Run Alignment Scan"):
        
        # 1. SCAN CURRICULUM
        st.info("Reading Curriculum...")
        regex_pattern = r"(KM-\d{2}(?:-KT\d{2})?)"
        topics_data = []
        
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
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
            st.error("No KM/KT codes found in Curriculum.")
        else:
            st.success(f"Found {len(unique_topics)} unique topics.")

            # 2. SCAN GUIDES
            all_hits = []
            progress_bar = st.progress(0)
            
            for g_idx, guide in enumerate(guide_files):
                with pdfplumber.open(guide) as pdf:
                    total_pages = len(pdf.pages)
                    
                    for page in pdf.pages:
                        p_num = page.page_number # This is the REAL page number
                        
                        # SKIP PAGES logic
                        if p_num <= pages_to_skip:
                            continue
                        
                        # CROP MARGINS logic
                        if ignore_margins:
                            h, w = float(page.height), float(page.width)
                            m = margin_percent / 100
                            # Crop: left, top, right, bottom
                            page_obj = page.crop((0, h * m, w, h * (1 - m)))
                        else:
                            page_obj = page
                            
                        text = page_obj.extract_text()
                        
                        if text:
                            for item in unique_topics:
                                # Use regex boundary \b to ensure exact matches
                                if re.search(r"\b" + re.escape(item["Code"]) + r"\b", text):
                                    all_hits.append({
                                        "Code": item["Code"],
                                        "Title": item["Title"],
                                        "Doc": guide.name,
                                        "Page": p_num
                                    })
                progress_bar.progress((g_idx + 1) / len(guide_files))

            # 3. CONSTRUCT OUTPUT
            if not all_hits:
                st.warning("No matches found in your guides. Check if codes are inside headers/footers.")
            else:
                df_hits = pd.DataFrame(all_hits)
                matrix = df_hits.groupby(['Code', 'Title', 'Doc'])['Page'].apply(condense_pages).unstack().reset_index()
                matrix = matrix.fillna("").sort_values(by="Code")

                st.write("### Final Alignment Results")
                st.dataframe(matrix, use_container_width=True)

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='QCTO_Alignment')
                
                st.download_button("📥 Download Excel Matrix", output.getvalue(), "QCTO_Alignment.xlsx")

else:
    st.info("Upload your Curriculum and Learning Materials to begin.")
