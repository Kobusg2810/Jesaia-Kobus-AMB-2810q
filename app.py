import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO Auditor-Ready Aligner", layout="wide")

st.title("📑 QCTO Accreditation Alignment Tool")
st.write("V7: Format-Agnostic Search (Ignores spaces, dashes, and dots)")

# --- CORE FUNCTIONS ---
def clean_for_search(text):
    """Removes all non-alphanumeric characters and converts to uppercase"""
    if not text: return ""
    return re.sub(r'[^A-Z0-9]', '', text.upper())

def get_condensed_pages(page_list, mode):
    if not page_list: return "NOT FOUND"
    pages = sorted(list(set([int(p) for p in page_list])))
    if not pages: return "NOT FOUND"
    
    if mode == "Starting Page Only":
        return str(pages[0])
    if mode == "Show All Pages":
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

# --- SIDEBAR ---
with st.sidebar:
    st.header("Audit Settings")
    page_mode = st.radio(
        "Page Numbering Style:",
        ["Show All Pages", "Condensed (e.g. 4-6, 12)", "Starting Page Only"],
        index=1
    )
    st.markdown("---")
    skip_toc = st.number_input("Ignore first X pages of Guide", value=0)
    st.info("Set this to 0 first to ensure nothing is missed.")

# --- MAIN INTERFACE ---
col1, col2 = st.columns(2)
with col1:
    curr_file = st.file_uploader("1. QCTO Curriculum (Source PDF)", type="pdf")
with col2:
    guide_files = st.file_uploader("2. Learner/Facilitator Guides (Target PDFs)", type="pdf", accept_multiple_files=True)

if curr_file and guide_files:
    if st.button("🔍 START ACCREDITATION SCAN"):
        
        # 1. SCAN CURRICULUM
        st.info("Step 1: Extracting KM/KT codes from Curriculum...")
        # Catch anything that looks like KM...KT...
        regex_pattern = r"(KM\s?[-.]?\s?\d{2,}(?:\s?[-.]?\s?KT\s?\d{2,})?)"
        
        curriculum_topics = []
        with pdfplumber.open(curr_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for line in text.split('\n'):
                        match = re.search(regex_pattern, line, re.IGNORECASE)
                        if match:
                            raw_code = match.group(0)
                            # Display version (clean looking)
                            display_code = raw_code.strip().upper()
                            # Search version (no symbols)
                            search_key = clean_for_search(raw_code)
                            
                            title = line.replace(raw_code, "").strip(": -–—.")
                            curriculum_topics.append({
                                "SearchKey": search_key, 
                                "DisplayCode": display_code, 
                                "Title": title[:100]
                            })

        df_curr = pd.DataFrame(curriculum_topics).drop_duplicates(subset=['SearchKey'])
        
        if df_curr.empty:
            st.error("No KM or KT codes detected in Curriculum. Please check the PDF format.")
        else:
            st.success(f"Found {len(df_curr)} Topics in Curriculum.")
            with st.expander("Verify Identified Topics List"):
                st.table(df_curr[['DisplayCode', 'Title']])

            # 2. SCAN GUIDES
            st.info("Step 2: Scanning Guides for matches...")
            raw_hits = []
            
            for guide in guide_files:
                with pdfplumber.open(guide) as pdf:
                    for page in pdf.pages:
                        p_num = page.page_number
                        if p_num <= skip_toc: continue
                        
                        text = page.extract_text()
                        if text:
                            # Create a 'searchable fingerprint' of the entire page
                            page_fingerprint = clean_for_search(text)
                            
                            for _, row in df_curr.iterrows():
                                if row['SearchKey'] in page_fingerprint:
                                    raw_hits.append({
                                        "SearchKey": row['SearchKey'],
                                        "DisplayCode": row['DisplayCode'],
                                        "Title": row['Title'],
                                        "Doc": guide.name,
                                        "Page": p_num
                                    })

            # 3. BUILD MATRIX
            if not raw_hits:
                st.warning("No matches found in your guides. Ensure the KM/KT codes are written in the text of your documents.")
            else:
                matrix_data = []
                for _, topic in df_curr.iterrows():
                    entry = {
                        "KM/KT Code": topic['DisplayCode'],
                        "Topic Description": topic['Title']
                    }
                    
                    for doc in guide_files:
                        matching_pages = [
                            h['Page'] for h in raw_hits 
                            if h['SearchKey'] == topic['SearchKey'] and h['Doc'] == doc.name
                        ]
                        entry[doc.name] = get_condensed_pages(matching_pages, page_mode)
                    
                    matrix_data.append(entry)

                final_df = pd.DataFrame(matrix_data)
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
else:
    st.info("Upload your Curriculum and Guides to begin.")
