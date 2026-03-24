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

def condense_pages(page_list):
    """Helper to turn [5, 6, 7, 10] into '5-7, 10'"""
    if not page_list: return ""
    pages = sorted(list(set(page_list)))
    if page_format == "First Mention Only":
        return str(pages[0])
    if page_format == "All Mentions":
        return ", ".join(map(str, pages))
    
    # Condensed Logic
    ranges = []
    if not pages: return ""
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
                    # Find codes and the text immediately following them (the title)
                    lines = text.split('\n')
                    for line in lines:
                        match = re.search(regex_pattern, line)
                        if match:
                            code = match.group(0)
                            # Try to clean up the rest of the line to use as a title
                            title = line.replace(code, "").strip(": -")
                            topics_data.append({"Code": code, "Title": title[:100]})

        # Remove duplicates while keeping order
        unique_topics = []
        seen = set()
        for t in topics_data:
            if t["Code"] not in seen:
                unique_topics.append(t)
                seen.add(t["Code"])
        
        if not unique_topics:
            st.error("Could not find any KM or KT codes. Please check document format.")
        else:
            st.success(f"Found {len(unique_topics)} items (KMs and KTs). Scanning guides...")

            # 2. SCAN GUIDES FOR THOSE CODES
            all_hits = []
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for i, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        if text:
                            for item in unique_topics:
                                if item["Code"] in text:
                                    all_hits.append({
                                        "Code": item["Code"],
                                        "Title": item["Title"],
                                        "Doc": guide.name,
                                        "Page": i
                                    })

            if not all_hits:
                st.warning("No matches found in your guides. Ensure codes like 'KM-01-KT01' are written in the text.")
            else:
                # 3. GROUP AND FORMAT RESULTS
                df_hits = pd.DataFrame(all_hits)
                
                # Group by Code, Title, and Doc to condense the pages
                matrix = df_hits.groupby(['Code', 'Title', 'Doc'])['Page'].apply(condense_pages).unstack().reset_index()
                
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
                    file_name="QCTO_Alignment_Matrix_Refined.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

else:
    st.info("Upload your files above to start.")
