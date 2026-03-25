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
    st.header("Matrix Settings")
    page_format = st.selectbox(
        "Page Number Format",
        ["First Mention Only", "Condensed (e.g., 5, 8-10)", "All Mentions"]
    )
    st.info("Tip: Auditors usually prefer 'First Mention' or 'Condensed'.")

def condense_pages(series):
    """Helper to turn a pandas series of pages into a nice string like '5-7, 10'"""
    if series.empty:
        return ""
    
    # Convert to a sorted list of unique integers
    pages = sorted(list(set(series.dropna().astype(int).tolist())))
    
    if not pages:
        return ""

    if page_format == "First Mention Only":
        return str(pages[0])
    
    if page_format == "All Mentions":
        return ", ".join(map(str, pages))
    
    # Condensed Logic (Standard)
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
    if st.button("🚀 Generate Refined Alignment Matrix"):
        
        # 1. SCAN CURRICULUM FOR KMs AND KTs
        st.write("🔍 Extracting Modules and Topics from Curriculum...")
        # Pattern to find KM-01 or KM-01-KT01
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
            st.error("Could not find any KM or KT codes in the Curriculum. Please check the PDF format.")
        else:
            st.success(f"Found {len(unique_topics)} items. Scanning guides...")

            # 2. SCAN GUIDES FOR THOSE CODES
            all_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        if text:
                            for item in unique_topics:
                                # Look for the exact code in the text
                                if item["Code"] in text:
                                    all_hits.append({
                                        "Code": item["Code"],
                                        "Title": item["Title"],
                                        "Doc": guide.name,
                                        "Page": i
                                    })

            if not all_hits:
                st.warning("No matches found in your guides. Ensure codes like 'KM-01-KT01' are written in the text of your documents.")
            else:
                # 3. GROUP AND FORMAT RESULTS
                df_hits = pd.DataFrame(all_hits)
                
                # Apply the fixed condense_pages function
                matrix = df_hits.groupby(['Code', 'Title', 'Doc'])['Page'].apply(condense_pages).unstack().reset_index()
                
                # Replace NaN with empty string for a cleaner look
                matrix = matrix.fillna("")
                
                # Reorder so KMs and KTs are sorted naturally
                matrix = matrix.sort_values(by="Code")

                st.write("### Final Alignment Matrix")
                st.dataframe(matrix, use_container_width=True)

                # 4. EXPORT
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='Alignment')
                
                st.download_button(
                    "📥 Download Professional Matrix (Excel)",
                    data=output.getvalue(),
                    file_name="QCTO_Alignment_Matrix.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

else:
    st.info("Upload your files above to start.")
