def run_bank_section():
    import streamlit as st
    import pandas as pd
    import fitz  # PyMuPDF
    import re
    import io
    import zipfile
    import numpy as np  # For integer conversion
    import time  # For timing
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # Read-only annotation flag (prevents moving/editing in most PDF viewers)
    ANNOT_FLAG_READONLY = 64

   

    # ----------------------- Helper Functions -----------------------
    def mask_non_highlighted_content(page, highlight_rects, all_rows, header_rows, footer_rows):
        """
        Masks all main content rows that are not highlighted (ignoring header and footer rows).
        Returns the number of mask annotations added.
        """
        mask_count_here = 0
        for row in all_rows:
            if row not in highlight_rects and row not in header_rows and row not in footer_rows:
                mask_annot = page.add_rect_annot(row)
                mask_annot.set_colors(stroke=(0.5, 0.5, 0.5), fill=(0.5, 0.5, 0.5))  # Gray mask
                mask_annot.set_border(width=1)
                mask_annot.set_opacity(1.0)
                mask_annot.set_flags(ANNOT_FLAG_READONLY)
                mask_annot.update()
                mask_count_here += 1
        return mask_count_here

    def highlight_and_mask_pdf_pages(pdf_file, unit_bank_dict, masking_mode, page_selection_mode):
        """
        Processes one PDF file:
          - In "Relevant Pages" mode, pages with no match are skipped (except the last page).
          - Each page is processed by grouping words into rows.
          - Rows are classified as header (top), footer (bottom), or main content.
          - Bank account matches and unit names are highlighted.
          - If masking mode is selected, non-highlighted main content rows are masked.
        Returns a tuple:
           ({ unit: [list of 1-page docs with modifications] },
            highlight_count, mask_count, unit_matched_local)
        """
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        bank_regex = re.compile(r"\b\d+\b")  # Pure digits only
        total_pages = doc.page_count

        local_highlight_count = 0
        local_mask_count = 0

        # Prepare a list (one entry per page) per unit.
        unit_pages = {unit: [None] * total_pages for unit in unit_bank_dict.keys()}
        unit_matched_local = {unit: set() for unit in unit_bank_dict.keys()}

        for i in range(total_pages):
            page = doc[i]
            words = page.get_text("words")

            for unit, bank_acc_list in unit_bank_dict.items():
                # Check if page has any bank account match.
                has_match = any(
                    bank_regex.fullmatch(w[4]) and w[4] in bank_acc_list
                    for w in words
                )
                # In Relevant Pages mode, skip pages without a match (except the last page).
                if page_selection_mode == "Relevant Pages" and not has_match and i != total_pages - 1:
                    continue

                # Create a temporary PDF for this page.
                temp_doc = fitz.open()
                temp_doc.insert_pdf(doc, from_page=i, to_page=i)
                temp_page = temp_doc[0]

                # Define thresholds for header and footer:
                header_threshold = temp_page.rect.height * (0.30 if i == 0 else 0.12)
                footer_threshold = temp_page.rect.height * 0.95

                all_rows = set()
                header_rows = set()
                footer_rows = set()
                highlight_rects = []

                for w in words:
                    word_text = w[4]
                    # Group words by similar y-coordinate to define a row.
                    row_words = [w] + [tw for tw in words if abs(tw[1] - w[1]) < 10]
                    x0 = min(rw[0] for rw in row_words)
                    y0 = min(rw[1] for rw in row_words)
                    x1 = max(rw[2] for rw in row_words)
                    y1 = max(rw[3] for rw in row_words)
                    row_rect = fitz.Rect(x0, y0, x1, y1)

                    # Classify the row as header, footer, or main content.
                    if y0 < header_threshold:
                        header_rows.add(row_rect)
                    elif y1 > footer_threshold:
                        footer_rows.add(row_rect)
                    else:
                        all_rows.add(row_rect)

                    # If the word is a bank account match, highlight that row.
                    if bank_regex.fullmatch(word_text) and word_text in bank_acc_list:
                        highlight_rects.append(row_rect)
                        annot = temp_page.add_rect_annot(row_rect)
                        annot.set_colors(stroke=(1, 1, 0), fill=(1, 1, 0))  # Yellow highlight
                        annot.set_border(width=1)
                        annot.set_opacity(0.3)
                        annot.set_flags(ANNOT_FLAG_READONLY)
                        annot.update()
                        unit_matched_local[unit].add(word_text)
                        local_highlight_count += 1

                # Optionally highlight the unit name itself.
                unit_rects = temp_page.search_for(unit)
                for rect in unit_rects:
                    highlight_rects.append(rect)
                    unit_annot = temp_page.add_rect_annot(rect)
                    unit_annot.set_colors(stroke=(1, 1, 0), fill=(1, 1, 0))
                    unit_annot.set_border(width=1)
                    unit_annot.set_opacity(0.5)
                    unit_annot.set_flags(ANNOT_FLAG_READONLY)
                    unit_annot.update()
                    local_highlight_count += 1

                # If "Mask all not relevant" is chosen, mask all main content rows that are not highlighted.
                if masking_mode == "Mask all not relevant":
                    mask_added = mask_non_highlighted_content(temp_page, highlight_rects, all_rows, header_rows, footer_rows)
                    local_mask_count += mask_added

                # Store the temp_doc in the unit_pages structure.
                unit_pages[unit][i] = temp_doc

        doc.close()
        # Remove None pages.
        result = {unit: [p for p in pages if p is not None] for unit, pages in unit_pages.items()}
        result = {unit: docs for unit, docs in result.items() if docs}
        return result, local_highlight_count, local_mask_count, unit_matched_local

    # ----------------------- Streamlit Layout -----------------------

    st.title("Bank Statment")

    # --- Step 1 & Step 2: Side-by-Side Columns for File Upload ---
    col_pdf, col_excel = st.columns(2)

    with col_pdf:
        st.header("Upload PDF files")
        pdf_files = st.file_uploader(
            "Upload one or more PDF files",
            type="pdf",
            accept_multiple_files=True
        )

    with col_excel:
        st.header("Upload Excel file")
        excel_file = st.file_uploader(
            "Upload an Excel file (.xlsx or .xls)",
            type=["xlsx", "xls"]
        )

    # Step 3: Choose Processing Options
    st.header("Choose Processing Options")

    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

    with col1:
        masking_mode = st.radio(
            "Select masking mode:",
            options=["Mask all not relevant", "Highlight Relevant"],
            index=0
        )

    with col2:
        page_selection_mode = st.radio(
            "Select Page Mode:",
            options=["All Pages", "Relevant Pages"],
            index=0
        )

    with col3:
        selected_month = st.selectbox(
            "Select Month",
            options=["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
        )

    with col4:
        selected_year = st.number_input("Select Year", min_value=2000, max_value=2100, step=1, value=2025)

    generate_button = st.button("Generate")

    # Step 4: Processing & Download
    st.header("Processing & Download")

    if generate_button:
        if not (pdf_files and excel_file):
            st.warning("Please upload at least one PDF and one Excel file to proceed.")
            st.stop()

        try:
            start_time = time.time()
            highlight_count = 0
            mask_count = 0

            # Read Excel file and build unit-bank dictionary.
            df = pd.read_excel(excel_file, dtype={'BANK_ACC_NO': str})
            unit_bank_dict = {}
            for _, row in df.iterrows():
                unit = row['UNIT']
                bank_acc = row['BANK_ACC_NO']
                unit_bank_dict.setdefault(unit, []).append(bank_acc)

            # If no valid data found in Excel, display mismatch message and stop.
            if not unit_bank_dict:
                st.error("The Excel file does not contain valid UNIT or BANK_ACC_NO data. (Mismatch file)")
                st.stop()

            combined_unit_matched = {unit: set() for unit in unit_bank_dict.keys()}

        except Exception as e:
            st.error("Error reading Excel file. Please check the file and column names.")
            st.error(e)
            st.stop()

        # Set up progress bar.
        progress_bar = st.progress(0)
        progress_text = st.empty()
        total_pdfs = len(pdf_files)
        completed = 0

        # Dictionary to hold final PDF docs for each unit.
        all_unit_docs = {u: [] for u in unit_bank_dict.keys()}

        # Process PDFs concurrently.
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for pdf in pdf_files:
                futures.append(executor.submit(
                    highlight_and_mask_pdf_pages,
                    pdf,
                    unit_bank_dict,
                    masking_mode,
                    page_selection_mode
                ))
            for future in as_completed(futures):
                pdf_result, local_h_count, local_m_count, unit_matched_pdf = future.result()
                highlight_count += local_h_count
                mask_count += local_m_count
                for unit, doc_list in pdf_result.items():
                    all_unit_docs[unit].extend(doc_list)
                for unit, matches in unit_matched_pdf.items():
                    combined_unit_matched[unit].update(matches)
                completed += 1
                progress = completed / total_pdfs
                progress_bar.progress(progress)
                elapsed = time.time() - start_time
                avg_time = elapsed / completed if completed > 0 else 0
                est_total = avg_time * total_pdfs
                remaining = est_total - elapsed
                progress_text.text(
                    f"Processed {completed}/{total_pdfs} PDFs. "
                    f"{progress*100:.0f}% complete. Estimated time remaining: {remaining:.1f} sec."
                )

        # Merge pages per unit into one PDF only if there is at least one highlight for that unit.
        unit_pdf_data = {}
        for unit, doc_list in all_unit_docs.items():
            if doc_list and combined_unit_matched[unit]:
                merged_pdf = fitz.open()
                for d in doc_list:
                    merged_pdf.insert_pdf(d)
                    d.close()
                pdf_bytes = merged_pdf.write()
                merged_pdf.close()
                unit_pdf_data[unit] = pdf_bytes

        # Prepare Excel files per unit (Matched / Unmatched).
        unit_excel_data = {}
        for unit in unit_bank_dict.keys():
            unit_df = df[df['UNIT'] == unit]
            matched_df = unit_df[unit_df['BANK_ACC_NO'].isin(combined_unit_matched[unit])]
            unmatched_df = unit_df[~unit_df['BANK_ACC_NO'].isin(combined_unit_matched[unit])]

            matched_buffer = io.BytesIO()
            with pd.ExcelWriter(matched_buffer, engine="xlsxwriter") as writer:
                matched_df.to_excel(writer, index=False, sheet_name="Matched")
            matched_bytes = matched_buffer.getvalue()

            unmatched_buffer = io.BytesIO()
            with pd.ExcelWriter(unmatched_buffer, engine="xlsxwriter") as writer:
                unmatched_df.to_excel(writer, index=False, sheet_name="Unmatched")
            unmatched_bytes = unmatched_buffer.getvalue()

            unit_excel_data[unit] = (matched_bytes, unmatched_bytes)

        # If no matches found in any PDF, inform the user.
        if not unit_pdf_data:
            st.info("No matches found in any PDF. (Mismatch file)")
        else:
            # Create a ZIP for each unit (PDF + matched/unmatched Excel).
            unit_zip_data = {}
            for unit, pdf_bytes in unit_pdf_data.items():
                inmem_zip = io.BytesIO()
                with zipfile.ZipFile(inmem_zip, "w", zipfile.ZIP_DEFLATED) as z:
                    z.writestr(f"{unit}_Bank.pdf", pdf_bytes)
                    if unit in unit_excel_data:
                        matched_bytes, unmatched_bytes = unit_excel_data[unit]
                        z.writestr(f"{unit}_Matched.xlsx", matched_bytes)
                        z.writestr(f"{unit}_Unmatched.xlsx", unmatched_bytes)
                inmem_zip.seek(0)
                unit_zip_data[unit] = inmem_zip.getvalue()

            # Create a master ZIP containing all unit ZIPs.
            master_zip_buffer = io.BytesIO()
            with zipfile.ZipFile(master_zip_buffer, "w", zipfile.ZIP_DEFLATED) as master_zip:
                for unit, zip_data in unit_zip_data.items():
                    master_zip.writestr(f"{unit}_Folder.zip", zip_data)
            master_zip_buffer.seek(0)

            # Name the master ZIP using the selected month and year
            master_zip_name = f"{selected_month}-{selected_year}.zip"
            st.download_button(
                label="Download Output in ZIP",
                data=master_zip_buffer.getvalue(),
                file_name=master_zip_name,
                mime="application/zip"
            )

        end_time = time.time()
        elapsed_time = end_time - start_time
        st.success(
            f"Processing complete in {elapsed_time:.2f} seconds. "
            f"Highlight annotations: {highlight_count}, Mask annotations: {mask_count}."
        )
