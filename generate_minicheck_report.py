#!/usr/bin/env python3
"""
Generate a MiniCheck Analysis Report by copying relevant sections
verbatim from the TPO template document (preserving all XML formatting).

The 21 critical MiniCheck findings (C=X) are mapped to exact Heading 2
titles in the TPO template.  Only those sections — plus the standard
document structure (cover, ToC, Service Summary, General Overview,
Check Lists) — appear in the output.
"""

import copy
import re
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────
TEMPLATE_PATH = '/Users/I321356/Documents/claude_project/TPO_template.docx'
OUTPUT_PATH   = '/Users/I321356/Documents/claude_project/MiniCheck_Report.docx'

COVER_INFO = {
    'title':  'SAP HANA MiniCheck Analysis Report',
    'system': 'HAN',
    'date':   '2026/04/06',
    'author': 'Quincy Chen',
}

# Exact Heading 2 titles in the TPO template, ordered by CHID ascending.
# Each tuple: (CHID, exact_heading_text, action_plan_description)
CRITICAL_SECTIONS = [
    ('M0115', 'Significant Variation in SAP HANA Service Startup Times',
     'Significant Variation in SAP HANA Service Startup Times'),
    ('M0209', 'Outdated Linux Kernel Version',
     'Outdated Linux Kernel Version'),
    ('M0411', 'Host Memory Overallocation',
     'Host Memory Overallocation'),
    ('M0418', 'Host Memory Overallocation',
     'Host Memory Overallocation'),
    ('M0471', 'IPMM Memory Size reported as too small',
     'IPMM Memory Size reported as too small'),
    ('M0551', 'Inadequate SAP HANA Timezone Configuration',
     'Inadequate SAP HANA Timezone Configuration'),
    ('M0552', 'Inadequate SAP HANA Timezone Configuration',
     'Inadequate SAP HANA Timezone Configuration'),
    ('M0744', 'High SQL Cache Utilization caused by Statistics Server',
     'High SQL Cache Utilization caused by Statistics Server'),
    ('M0752', 'Data Retention of Statistics Server Histories',
     'Data Retention of Statistics Server Histories'),
    ('M0753', 'Data Retention of Statistics Server Histories',
     'Data Retention of Statistics Server Histories'),
    ('M0754', 'Data Retention of Statistics Server Histories',
     'Data Retention of Statistics Server Histories'),
    ('M0766', 'No Statistics Server Related Workload Class Active',
     'No Statistics Server Related Workload Class Active'),
    ('M0910', 'No recent Data Backup available',
     'No recent Data Backup available'),
    ('M0945', 'Short Backup Retention Period',
     'Short Backup Retention Period'),
    ('M1142', 'High SQL Cache Utilization caused by specific Tables',
     'High SQL Cache Utilization caused by specific Tables'),
    ('M1165', 'High SQL Cache Utilization caused by Statistics Server',
     'High SQL Cache Utilization caused by Statistics Server'),
    ('M1168', 'Delivered Statement Hints not implemented',
     'Delivered Statement Hints not implemented'),
    ('M1415', 'License Limit reached',
     'License Limit reached'),
    ('M1420', 'License Limit reached',
     'License Limit reached'),
    ('M2113', 'No regular detailed SAP HANA Consistency Checks in Place',
     'No regular detailed SAP HANA Consistency Checks in Place'),
    ('M2340', 'Utilization of deprecated SAP HANA Features',
     'Utilization of deprecated SAP HANA Features'),
]

# Unique ordered section titles (deduped, preserving first CHID order)
def _unique_sections():
    seen = set()
    result = []
    for chid, heading, desc in CRITICAL_SECTIONS:
        if heading not in seen:
            seen.add(heading)
            result.append((chid, heading, desc))
    return result

UNIQUE_SECTIONS = _unique_sections()

# Action plan rows: one row per unique heading (mapped from CHID list)
def _action_plan_rows():
    seen = {}
    for chid, heading, desc in CRITICAL_SECTIONS:
        if heading not in seen:
            seen[heading] = {'chids': [chid], 'desc': desc}
        else:
            seen[heading]['chids'].append(chid)
    rows = []
    for heading, info in seen.items():
        rows.append({
            'heading': heading,
            'chids': ', '.join(info['chids']),
            'desc': info['desc'],
        })
    return rows

ACTION_PLAN_ROWS = _action_plan_rows()

HEADING_STYLES = {'Heading 1', 'Heading 2', 'Heading 3', 'Heading 4',
                  'berschrift 1', 'berschrift 2', 'berschrift 3', 'berschrift 4'}

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_heading(para):
    return para.style.name in HEADING_STYLES or para.style.name.startswith('Heading')


def _heading_level(para):
    m = re.search(r'\d+', para.style.name)
    return int(m.group()) if m else 99


def _para_text(para):
    return ''.join(r.text or '' for r in para.runs).strip()


def find_exact_section(doc, exact_title):
    """
    Find the Heading 2 paragraph whose text exactly matches exact_title,
    then collect all body elements up to (but not including) the next H2 or H1.
    Returns list of lxml elements, or None if not found.
    """
    body_children = list(doc.element.body)
    elem_to_para = {id(p._element): p for p in doc.paragraphs}

    for i, elem in enumerate(body_children):
        if id(elem) not in elem_to_para:
            continue
        para = elem_to_para[id(elem)]
        if not _is_heading(para):
            continue
        if _heading_level(para) != 2:
            continue
        if _para_text(para) != exact_title:
            continue

        # Found — collect up to next H1 or H2
        section_elems = []
        for j in range(i, len(body_children)):
            child = body_children[j]
            if j > i and id(child) in elem_to_para:
                p2 = elem_to_para[id(child)]
                if _is_heading(p2) and _heading_level(p2) <= 2:
                    break
            section_elems.append(child)
        return section_elems

    return None


def find_heading1_section(doc, h1_text):
    """
    Find an H1 paragraph whose text contains h1_text, then collect all body
    elements until the next H1.
    Returns list of lxml elements, or None.
    """
    body_children = list(doc.element.body)
    elem_to_para = {id(p._element): p for p in doc.paragraphs}

    for i, elem in enumerate(body_children):
        if id(elem) not in elem_to_para:
            continue
        para = elem_to_para[id(elem)]
        if not _is_heading(para):
            continue
        if _heading_level(para) != 1:
            continue
        if h1_text.lower() not in _para_text(para).lower():
            continue

        section_elems = []
        for j in range(i, len(body_children)):
            child = body_children[j]
            if j > i and id(child) in elem_to_para:
                p2 = elem_to_para[id(child)]
                if _is_heading(p2) and _heading_level(p2) == 1:
                    break
            section_elems.append(child)
        return section_elems

    return None


def find_cover_elements(doc):
    """Return all body elements before the first H1 or ToC heading."""
    body_children = list(doc.element.body)
    elem_to_para = {id(p._element): p for p in doc.paragraphs}
    result = []
    for elem in body_children:
        if id(elem) in elem_to_para:
            para = elem_to_para[id(elem)]
            if _is_heading(para) and _heading_level(para) == 1:
                break
            # Stop at anything that looks like a ToC heading
            t = _para_text(para).strip().lower()
            if t in ('table of contents', 'contents', 'inhaltsverzeichnis'):
                break
        result.append(elem)
    return result


def append_elements(target_body, elements):
    for elem in elements:
        target_body.append(copy.deepcopy(elem))


# ──────────────────────────────────────────────────────────────────────────────
# Word auto-ToC field
# ──────────────────────────────────────────────────────────────────────────────

def _make_toc_field():
    """Return an lxml <w:p> containing a Word automatic TOC field."""
    nsmap = {'w': W_NS}

    p = OxmlElement('w:p')

    # Paragraph style = "TOC Heading" or plain
    pPr = OxmlElement('w:pPr')
    pStyle = OxmlElement('w:pStyle')
    pStyle.set(qn('w:val'), 'TOCHeading')
    pPr.append(pStyle)
    p.append(pPr)

    # fldChar begin
    r1 = OxmlElement('w:r')
    fc1 = OxmlElement('w:fldChar')
    fc1.set(qn('w:fldCharType'), 'begin')
    fc1.set(qn('w:dirty'), 'true')
    r1.append(fc1)
    p.append(r1)

    # instrText
    r2 = OxmlElement('w:r')
    instr = OxmlElement('w:instrText')
    instr.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    r2.append(instr)
    p.append(r2)

    # fldChar separate
    r3 = OxmlElement('w:r')
    fc3 = OxmlElement('w:fldChar')
    fc3.set(qn('w:fldCharType'), 'separate')
    r3.append(fc3)
    p.append(r3)

    # placeholder text
    r4 = OxmlElement('w:r')
    rPr4 = OxmlElement('w:rPr')
    noProof = OxmlElement('w:noProof')
    rPr4.append(noProof)
    r4.append(rPr4)
    t4 = OxmlElement('w:t')
    t4.text = 'Right-click here and choose "Update Field" to refresh table of contents'
    r4.append(t4)
    p.append(r4)

    # fldChar end
    r5 = OxmlElement('w:r')
    fc5 = OxmlElement('w:fldChar')
    fc5.set(qn('w:fldCharType'), 'end')
    r5.append(fc5)
    p.append(r5)

    return p


# ──────────────────────────────────────────────────────────────────────────────
# Action Plan table builder
# ──────────────────────────────────────────────────────────────────────────────

def _find_action_plan_table(doc):
    """
    Find the Action Plan table in the template: the first table that follows
    an H2 paragraph containing 'Action Plan'.
    Returns (table_object, section_elements_including_heading).
    """
    body_children = list(doc.element.body)
    elem_to_para = {id(p._element): p for p in doc.paragraphs}
    tables_map = {id(t._element): t for t in doc.tables}

    found_heading = False
    heading_idx = -1

    for i, elem in enumerate(body_children):
        if not found_heading:
            if id(elem) in elem_to_para:
                para = elem_to_para[id(elem)]
                if _is_heading(para) and 'action plan' in _para_text(para).lower():
                    found_heading = True
                    heading_idx = i
        else:
            if id(elem) in tables_map:
                return tables_map[id(elem)], heading_idx, i
    return None, -1, -1


def _cell_text(cell):
    return '\n'.join(p.text for p in cell.paragraphs).strip()


def _make_action_plan_section(src_doc, rows):
    """
    Copy the Action Plan heading from the template, then rebuild the table
    keeping only the header row and one row per item in `rows`.
    Returns list of lxml elements to append.
    """
    table, heading_idx, table_idx = _find_action_plan_table(src_doc)
    if table is None:
        print('  [WARNING] Action Plan table not found in template')
        return []

    body_children = list(src_doc.element.body)
    result_elems = []

    # Copy elements from the heading up to (but not including) the table
    for i in range(heading_idx, table_idx):
        result_elems.append(copy.deepcopy(body_children[i]))

    # Rebuild the table: header row + filtered/renumbered data rows
    src_rows = table.rows
    if not src_rows:
        return result_elems

    new_table = copy.deepcopy(table._element)
    # Remove all rows from the copy
    tbl_elem = new_table
    for tr in list(tbl_elem.findall(f'{{{W_NS}}}tr')):
        tbl_elem.remove(tr)

    # Re-add header row verbatim
    header_tr = copy.deepcopy(src_rows[0]._element)
    tbl_elem.append(header_tr)

    # Find a template data row to clone
    template_data_row = src_rows[1]._element if len(src_rows) > 1 else src_rows[0]._element

    for seq_num, row_info in enumerate(rows, start=1):
        new_tr = copy.deepcopy(template_data_row)
        cells = new_tr.findall(f'.//{{{W_NS}}}tc')
        if len(cells) >= 4:
            # Cell 0: ID
            _set_cell_text(cells[0], str(seq_num))
            # Cell 1: Issue / heading title
            _set_cell_text(cells[1], row_info['heading'])
            # Cell 2: MiniCheck IDs
            _set_cell_text(cells[2], row_info['chids'])
            # Cell 3: leave as-is (recommendation placeholder) or blank
        tbl_elem.append(new_tr)

    result_elems.append(tbl_elem)
    return result_elems


def _set_cell_text(tc_elem, text):
    """Clear all paragraphs in a table cell and set plain text."""
    paras = tc_elem.findall(f'{{{W_NS}}}p')
    if not paras:
        p = OxmlElement('w:p')
        tc_elem.append(p)
        paras = [p]
    # Use first paragraph, clear its runs
    p = paras[0]
    for r in list(p.findall(f'{{{W_NS}}}r')):
        p.remove(r)
    r = OxmlElement('w:r')
    t = OxmlElement('w:t')
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    r.append(t)
    p.append(r)
    # Remove extra paragraphs
    for extra_p in paras[1:]:
        tc_elem.remove(extra_p)


# ──────────────────────────────────────────────────────────────────────────────
# ToC heading paragraph from template
# ──────────────────────────────────────────────────────────────────────────────

def find_toc_heading(doc):
    """Find the Table of Contents heading paragraph element."""
    for para in doc.paragraphs:
        t = _para_text(para).strip().lower()
        if t in ('table of contents', 'contents', 'inhaltsverzeichnis',
                 'table of content'):
            return copy.deepcopy(para._element)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main(output_path=None):
    global OUTPUT_PATH
    if output_path:
        # Resolve relative paths against the project directory
        import os
        if not os.path.isabs(output_path):
            output_path = os.path.join('/Users/I321356/Documents/claude_project', output_path)
        OUTPUT_PATH = output_path

    print(f'Opening template: {TEMPLATE_PATH}')
    src_doc = Document(TEMPLATE_PATH)

    print('Creating output document from template (styles/themes preserved)…')
    out_doc = Document(TEMPLATE_PATH)
    body = out_doc.element.body
    for child in list(body):
        body.remove(child)

    # ── 1. Cover page (verbatim from template) ────────────────────────────────
    print('\n[1/6] Copying cover page…')
    cover_elems = find_cover_elements(src_doc)
    print(f'      {len(cover_elems)} elements copied')
    append_elements(body, cover_elems)

    # ── 2. Table of Contents heading + auto-field ─────────────────────────────
    print('\n[2/6] Adding Table of Contents heading + auto-field…')
    toc_heading = find_toc_heading(src_doc)
    if toc_heading is not None:
        body.append(toc_heading)
    else:
        # Fallback: create a plain heading
        p = OxmlElement('w:p')
        pPr = OxmlElement('w:pPr')
        pStyle = OxmlElement('w:pStyle')
        pStyle.set(qn('w:val'), 'Heading1')
        pPr.append(pStyle)
        p.append(pPr)
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = 'Table of Contents'
        r.append(t)
        p.append(r)
        body.append(p)

    body.append(_make_toc_field())
    body.append(OxmlElement('w:p'))  # blank after ToC

    # ── 3. Service Summary (H1 with Executive Summary + Action Plan) ──────────
    print('\n[3/6] Copying Service Summary section…')
    # Copy Executive Summary sub-section
    exec_summary = find_heading1_section(src_doc, 'Service Summary')
    if exec_summary:
        # Only take up to (but not including) the next H1 — already done by helper
        # But we need to replace the Action Plan table with a filtered one
        # Find where Action Plan starts within exec_summary elements
        tpl_body_children = list(src_doc.element.body)
        elem_to_para = {id(p._element): p for p in src_doc.paragraphs}

        ap_heading_local = None
        for i, elem in enumerate(exec_summary):
            if id(elem) in elem_to_para:
                p = elem_to_para[id(elem)]
                if _is_heading(p) and 'action plan' in _para_text(p).lower():
                    ap_heading_local = i
                    break

        if ap_heading_local is not None:
            # Copy everything before action plan heading
            append_elements(body, exec_summary[:ap_heading_local])
            # Now add the rebuilt action plan section
            print('      Rebuilding Action Plan table…')
            ap_elems = _make_action_plan_section(src_doc, ACTION_PLAN_ROWS)
            for e in ap_elems:
                body.append(e)
        else:
            append_elements(body, exec_summary)
        print(f'      Service Summary: {len(exec_summary)} elements')
    else:
        print('      [WARNING] Service Summary not found in template')

    # ── 4. General Overview (H1) ──────────────────────────────────────────────
    print('\n[4/6] Copying General Overview section…')
    gen_overview = find_heading1_section(src_doc, 'General Overview')
    if gen_overview:
        append_elements(body, gen_overview)
        print(f'      {len(gen_overview)} elements copied')
    else:
        print('      [WARNING] General Overview not found in template')

    # ── 5. Check Lists (H1) ───────────────────────────────────────────────────
    print('\n[5/6] Copying Check Lists section…')
    check_lists = find_heading1_section(src_doc, 'Check List')
    if check_lists:
        append_elements(body, check_lists)
        print(f'      {len(check_lists)} elements copied')
    else:
        print('      [WARNING] Check Lists not found in template')

    # ── 6. Issues and Recommendations (H1 heading + exact H2 subsections) ─────
    print('\n[6/6] Adding Issues and Recommendations sections…')

    # Add H1 heading
    issues_h1 = find_heading1_section(src_doc, 'Issues and Recommendation')
    if issues_h1:
        # Only copy the H1 paragraph itself (first element)
        body.append(copy.deepcopy(issues_h1[0]))
    else:
        p = OxmlElement('w:p')
        pPr = OxmlElement('w:pPr')
        pStyle = OxmlElement('w:pStyle')
        pStyle.set(qn('w:val'), 'Heading1')
        pPr.append(pStyle)
        p.append(pPr)
        r = OxmlElement('w:r')
        t = OxmlElement('w:t')
        t.text = 'Issues and Recommendations'
        r.append(t)
        p.append(r)
        body.append(p)

    not_found = []
    added_headings = set()

    for chid, heading_title, _ in UNIQUE_SECTIONS:
        if heading_title in added_headings:
            continue
        elems = find_exact_section(src_doc, heading_title)
        if elems:
            append_elements(body, elems)
            added_headings.add(heading_title)
            print(f'      [OK] {chid}: {heading_title!r} ({len(elems)} elements)')
        else:
            not_found.append((chid, heading_title))
            print(f'      [--] {chid}: {heading_title!r} NOT FOUND — adding placeholder')
            add_placeholder_section(body, heading_title, chid)

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f'\nSaving output to: {OUTPUT_PATH}')
    out_doc.save(OUTPUT_PATH)
    print('Done — output file created successfully.')

    return not_found


def add_placeholder_section(target_body, title, chid):
    h_para = OxmlElement('w:p')
    h_pPr = OxmlElement('w:pPr')
    h_style = OxmlElement('w:pStyle')
    h_style.set(qn('w:val'), 'Heading2')
    h_pPr.append(h_style)
    h_para.append(h_pPr)
    h_run = OxmlElement('w:r')
    h_t = OxmlElement('w:t')
    h_t.text = title
    h_run.append(h_t)
    h_para.append(h_run)
    target_body.append(h_para)

    n_para = OxmlElement('w:p')
    n_run = OxmlElement('w:r')
    n_t = OxmlElement('w:t')
    n_t.text = f'[MiniCheck {chid}] — section not found verbatim in template.'
    n_run.append(n_t)
    n_para.append(n_run)
    target_body.append(n_para)
    target_body.append(OxmlElement('w:p'))


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else None
    not_found = main(output_path=out)
    if not_found:
        print('\nSections not found in template:')
        for chid, title in not_found:
            print(f'  {chid}: {title}')
