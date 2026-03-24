import streamlit as st
import pdfplumber
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="QCTO KM/KT Aligner", layout="wide")

st.title("📑 QCTO KM & KT Alignment Tool")
st.write("This tool extracts KM/KT codes from your Curriculum and finds their page numbers in your Guides.")

# --- STEP 1: UPLOAD DOCUMENTS ---
col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Source Document")
    curriculum_file = st.file_uploader("Upload QCTO Curriculum (PDF)", type="pdf")

with col2:
    st.subheader("2. Target Documents")
    material_files = st.file_uploader("Upload Learner/Facilitator Guides (PDFs)", type="pdf", accept_multiple_files=True)

# --- PROCESSING LOGIC ---
if curriculum_file and material_files:
    if st.button("Generate KM/KT Matrix"):
        
        # 1. Extract KM and KT codes from the Curriculum
        # Regex explanation: KM-\d{2} finds KM-01, KT\d{2} finds KT01
        # Combined: KM-\d{2}-KT\d{2} finds the full topic code
        kt_pattern = r"KM-\d{2}-KT\d{2}"
        
        st.info("🔍 Analyzing Curriculum for KM/KT codes...")
        found_codes = []
        
        with pdfplumber.open(curriculum_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    matches = re.findall(kt_pattern, text)
                    found_codes.extend(matches)
        
        # Unique list of codes sorted
        unique_codes = sorted(list(set(found_codes)))
        
        if not unique_codes:
            st.error("No KM/KT codes found in the Curriculum PDF. Please check the format.")
        else:
            st.success(f"Found {len(unique_codes)} Knowledge Topics (KTs). Now scanning guides...")

            # 2. Search for these codes in the Learning Materials
            results = []
            
            for uploaded_file in material_files:
                with pdfplumber.open(uploaded_file) as pdf:
                    for page_num, page in enumerate(pdf.pages, 1):
                        text = page.extract_text()
                        if text:
                            for code in unique_codes:
                                # We search for the code (e.g., KM-01-KT01) in the text
                                if code in text:
                                    results.append({
                                        "KT Code": code,
                                        "Module": code[:5], # Extracts 'KM-01'
                                        "Document": uploaded_file.name,
                                        "Page": page_num
                                    })

            # 3. Process Results into Matrix
            if results:
                df = pd.DataFrame(results)
                
                # Group page numbers so they appear as "5, 12, 14" instead of separate rows
                matrix = df.groupby(['KT Code', 'Module', 'Document'])['Page'].apply(
                    lambda x: ', '.join(map(str, sorted(list(set(x)))))
                ).unstack().reset_index()

                st.write("### Final Alignment Matrix")
                st.dataframe(matrix, use_container_width=True)

                # 4. Excel Download
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    matrix.to_excel(writer, index=False, sheet_name='KM_KT_Alignment')
                
                st.download_button(
                    label="📥 Download Excel Alignment Matrix",
                    data=output.getvalue(),
                    file_name="QCTO_KM_KT_Matrix.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Codes were found in the curriculum, but none were found in your Learning Materials. Ensure the codes are typed exactly (e.g., KM-01-KT01) in your Word/PDF guides.")

else:
    st.info("Awaiting files. Please upload your Curriculum and at least one Guide.")
