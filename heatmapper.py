import os
import sys
import csv
import subprocess
from weasyprint import HTML
from PyPDF2 import PdfMerger

CARD_CSS = """
@page { size:A4 portrait; margin:.6in; }

body {
    font-family: Arial, sans-serif;
    font-size: 14pt;
    line-height: 1.35;
    color:#222;
}

.header {
    font-size: 18pt;
    font-weight: bold;
    border-bottom: 2px solid #333;
    margin-bottom: 14px;
}

.card {
    border:1px solid #d9d9d9;
    border-radius:12px;
    padding:14px 16px;
    margin:12px 0;
    background:#fafafa;
}

.section-title {
    font-weight:bold;
    font-size:12pt;
    margin-bottom:6px;
}

.hl {
    border-radius:8px;
    padding:2px 5px;
    box-decoration-break: clone;
    -webkit-box-decoration-break: clone;
}

.color-box {
    display:inline-block;
    width:30px;
    height:15px;
    margin-right:6px;
    border-radius:5px;
}
"""


def map_score_to_color(score):
    try:
        s = float(score)
    except Exception:
        s = 0.0
    if s > 85:
        return "#b7e4c7"   # pastel green
    elif s > 80:
        return "#ffe8a1"   # pastel yellow
    elif s > 75:
        return "#f7c6a3"   # pastel orange
    else:
        return "#f5a3a3"   # pastel red


def map_word_score_to_color(score):
    try:
        s = float(score)
    except Exception:
        s = 0.0
    if s > 95:
        return "#b7e4c7"
    elif s > 90:
        return "#ffe8a1"
    elif s > 80:
        return "#f7c6a3"
    else:
        return "#f5a3a3"

def escape_html(s):
    return (s.replace("&", "&amp;")
              .replace("<", "&lt;")
              .replace(">", "&gt;")
              .replace('"', "&quot;")
              .replace("'", "&#39;"))

def generate_heatmap_pdf(folder, rows):

    paragraph_html = "".join(
        f'<mark class="hl" style="background:{map_score_to_color(row.get("prosody_score", "0"))};">'
        f'{escape_html(row.get("reference_text", "").strip())}</mark> '
        for row in rows
        if row.get("recognized_text", "").strip()
    ).strip()

    html_content = f"""
    <html>
    <head>
    <style>
    @page {{ size:A4; margin:.45in; }}

    body {{
        font-family: Arial, sans-serif;
        font-size: 14pt;
        line-height: 1.35;
    }}

    .card {{
        border:1px solid #dddddd;
        border-radius:12px;
        padding:12px 14px;
        background:#fafafa;
        margin-bottom:12px;
        width:100%;
    }}

    .title {{
        font-weight:bold;
        font-size:12pt;
        margin-bottom:6px;
    }}

    .paragraph-text {{
        white-space: normal;
        line-height: 1.5;
    }}

    /* 🔥 mark highlight (no padding = stable) */
    mark.hl {{
        padding:3px 0;
        border-radius:5px;
        box-decoration-break:clone;
        -webkit-box-decoration-break:clone;
    }}

    .color-box {{
        display:inline-block;
        width:26px;
        height:14px;
        border-radius:4px;
        margin-right:6px;
        vertical-align:middle;
    }}
    </style>
    </head>

    <body>

    <div class="card">
    <div class="title">Analysis notes:</div>
    This PDF contains your text color‐coded according to overall speech quality as measured by the Microsoft Azure Pronunciation Assessment API.
    Try to improve your <span style="background:#b7e4c7;border-radius:6px;padding:2px 4px;">intonation, emphasis, and word/phrase stress</span> (collectively called prosody) to achieve higher levels of speech quality.
    </div>

    <div class="card">
    <div class="title">Contact info:</div>
    richard.rose@hufs.ac.kr<br>
    richard.rose@yonsei.ac.kr
    </div>

    <div class="card">
    <div class="title">Speech Quality and Color Scoring System:</div>
    <span class="color-box" style="background:#b7e4c7;"></span> Prosody > 85<br>
    <span class="color-box" style="background:#ffe8a1;"></span> Prosody > 80<br>
    <span class="color-box" style="background:#f7c6a3;"></span> Prosody > 75<br>
    <span class="color-box" style="background:#f5a3a3;"></span> Prosody ≤ 75
    </div>

    <div class="card">
    <div class="title">Your text:</div>
    <div class="paragraph-text">{paragraph_html}</div>
    </div>

    </body>
    </html>
    """

    pdf_path = os.path.join(folder, "heatmap.pdf")
    HTML(string=html_content).write_pdf(pdf_path)
    print(f"Generated heatmap PDF at {pdf_path}")

# New function to generate a word‐level heatmap PDF
def generate_word_heatmap_pdf(folder, rows):
    import os
    import re
    from weasyprint import HTML

    # ---------- color palette (card layout pastel set) ----------
    c95 = "#b7e4c7"  # green
    c90 = "#ffe8a1"  # yellow
    c80 = "#f7c6a3"  # orange (pastel)
    c0  = "#f5a3a3"  # red

    # ---------- build lookup ----------
    lookup = {
        (int(r["sentence_index"]), int(r["word_index"])): r
        for r in rows
    }

    # ---------- read original text ----------
    text_path = os.path.join(folder, "text.txt")
    with open(text_path, encoding="utf-8") as ft:
        full_text = ft.read().strip()

    sentences = re.split(r'(?<=[\.!?])\s+', full_text)

    # ---------- build highlighted word stream ----------
    words_html = ""

    # split full text exactly like your debug script
    tokens = re.split(r'\s+', full_text.strip())

    # pad tokens if CSV has more rows (your observed issue)
    if len(tokens) < len(rows):
        tokens += [""] * (len(rows) - len(tokens))

    for i, row in enumerate(rows):
        token = tokens[i] if i < len(tokens) else ""

        if not token:
            words_html += " "
            continue

        if row["error_type"].lower() not in ("none", "mispronunciation", "omission"):
            words_html += escape_html(token) + " "
            continue

        score = float(row.get("accuracy_score", "0") or 0)

        if score > 95:
            color = c95
        elif score > 90:
            color = c90
        elif score > 80:
            color = c80
        else:
            color = c0

        words_html += (
            f'<span class="hl-word" style="background:{color};">'
            f'{escape_html(token)}</span> '
        )

    # ---------- HTML ----------
    html_content = f"""
    <html>
    <head>
    <style>
    @page {{ size:A4; margin:.45in; }}

    body {{
        font-family: Arial, sans-serif;
        font-size: 14pt;
        line-height: 1.35;
    }}

    .card {{
        border:1px solid #dddddd;
        border-radius:12px;
        padding:12px 14px;
        background:#fafafa;
        margin-bottom:12px;
        width:100%;
    }}

    .title {{
        font-weight:bold;
        font-size:12pt;
        margin-bottom:6px;
    }}

    .hl-word {{
        border-radius:6px;
        padding:2px 5px;
        box-decoration-break:clone;
        -webkit-box-decoration-break:clone;
    }}

    .color-box {{
        display:inline-block;
        width:26px;
        height:14px;
        border-radius:4px;
        margin-right:6px;
        vertical-align:middle;
    }}
    </style>
    </head>

    <body>

    <div class="card">
    <div class="title">Analysis notes:</div>
    This PDF contains your text color‐coded according to pronunciation accuracy as measured by the Microsoft Azure Pronunciation Assessment API.
    Try to improve your <span style="background:#b7e4c7;border-radius:6px;padding:2px 4px;">consonant sounds and vowel sounds</span> to achieve higher levels of speech quality.
    </div>

    <div class="card">
    <div class="title">Contact info:</div>
    richard.rose@hufs.ac.kr<br>
    richard.rose@yonsei.ac.kr
    </div>

    <div class="card">
    <div class="title">Word Accuracy and Color Scoring System:</div>
    <span class="color-box" style="background:{c95};"></span> Accuracy > 95<br>
    <span class="color-box" style="background:{c90};"></span> Accuracy > 90<br>
    <span class="color-box" style="background:{c80};"></span> Accuracy > 80<br>
    <span class="color-box" style="background:{c0};"></span> Accuracy ≤ 80
    </div>

    <div class="card">
    <div class="title">Your words:</div>
    {words_html}
    </div>

    </body>
    </html>
    """

    # ---------- render ----------
    pdf_path = os.path.join(folder, "word_heatmap.pdf")
    HTML(string=html_content).write_pdf(pdf_path)
    print(f"Generated word-level heatmap PDF at {pdf_path}")

def generate_table_pdf(folder, rows, section_title, filename, landscape=False, wide_columns=None):
    headers = list(rows[0].keys())

    # --- REORDER: move pronunciation_score after recognized_text ---
    if "recognized_text" in headers and "pronunciation_score" in headers:
        headers.remove("pronunciation_score")
        insert_idx = headers.index("recognized_text") + 1
        headers.insert(insert_idx, "pronunciation_score")

    page_size = "A4 landscape" if landscape else "A4 portrait"
    processed_headers = [h.replace("_", " ") for h in headers]

    col_widths = []
    for idx, h in enumerate(headers):
        if wide_columns and idx in wide_columns:
            col_widths.append("width: 30%;")
        else:
            col_widths.append("width: auto;")

    table_rows = ""

    # --- NORMAL ROWS ---
    for row in rows:
        table_rows += "<tr>" + "".join(
            f'<td style="{col_widths[idx]}">{escape_html(str(row.get(h, "")))}</td>'
            for idx, h in enumerate(headers)
        ) + "</tr>"

    # --- ADD AVERAGE ROW (ONLY FOR SENTENCE TABLE) ---
    if "prosody_score" in headers:

        def safe_avg(key):
            vals = []
            for r in rows:
                try:
                    vals.append(float(r.get(key, 0)))
                except:
                    pass
            return round(sum(vals) / len(vals), 2) if vals else ""

        avg_row_html = "<tr>" + "".join(
            f'<td style="{col_widths[idx]}; font-weight:bold;">'
            + (
                "AVERAGE" if idx == 0 else
                str(safe_avg(h)) if h in (
                    "accuracy_score",
                    "pronunciation_score",
                    "prosody_score",
                    "fluency_score",
                    "completeness_score"
                ) else ""
            )
            + "</td>"
            for idx, h in enumerate(headers)
        ) + "</tr>"

        table_rows += avg_row_html

    html_content = f"""
    <html>
    <head>
        <style>
            @page {{
                size: {page_size};
                margin: 1in;
            }}
            body {{
                font-family: Arial, sans-serif;
                font-size: 10pt;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                page-break-inside: avoid;
            }}
            th, td {{
                border: 1px solid black;
                padding: 5px;
                text-align: left;
                vertical-align: top;
            }}
            th {{
                background-color: #f2f2f2;
                font-weight: bold;
            }}
            thead {{
                display: table-header-group;
            }}
            tr {{
                page-break-inside: avoid;
            }}
            .section-title-header {{
                font-weight: bold;
                font-size: 12pt;
                background-color: #e0e0e0;
                text-align: left;
                padding: 5px;
            }}
        </style>
    </head>
    <body>
        <table>
            <thead>
                <tr><th colspan="{len(headers)}" class="section-title-header">{section_title}</th></tr>
                <tr>{''.join(f'<th>{escape_html(h)}</th>' for h in processed_headers)}</tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
    </body>
    </html>
    """

    pdf_path = os.path.join(folder, filename)
    HTML(string=html_content).write_pdf(pdf_path)
    print(f"Generated {filename} at {pdf_path}")

def merge_pdfs(folder):
    merger = PdfMerger()
    pdf_files = ["heatmap.pdf", "word_heatmap.pdf", "sentences.pdf", "words.pdf"]

    for pdf in pdf_files:
        pdf_path = os.path.join(folder, pdf)
        if os.path.isfile(pdf_path):
            merger.append(pdf_path)

    combined_path = os.path.join(folder, "analysis.pdf")
    merger.write(combined_path)
    merger.close()
    print(f"Created combined PDF at {combined_path}")

def send_email_with_applescript(folder):
    applescript_code = f'''
    set folderPath to "{folder}"
    set emailFilePath to folderPath & "/email.txt"
    set nameFilePath to folderPath & "/name.txt"
    set pdfPath to folderPath & "/analysis.pdf"

    set emailaddy to do shell script "cat " & quoted form of emailFilePath
    set nameFileContent to do shell script "cat " & quoted form of nameFilePath

    set messageBody to "Hi " & nameFileContent & ",\\n\\n" & ¬
        "Thanks for submitting an audio recording for analysis and feedback.\\n\\n" & ¬
        "Your speech quality analysis is attached to this email.\\n" & ¬
        "The PDF file contains detailed feedback on your speech quality\\n" & ¬
        "at the paragraph, sentence, and word levels.\\n" & ¬
        "Please let me know if you have any further questions.\\n\\n" & ¬
        "Best regards,\\nDr. Rose"

    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"Speech Quality Analysis", content:messageBody, visible:true}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:emailaddy}}
            make new attachment with properties {{file name:(POSIX file pdfPath as alias)}} at after last paragraph
        end tell
        send newMessage
    end tell
    '''

    script_path = os.path.join(folder, "send_email.applescript")
    with open(script_path, "w") as script_file:
        script_file.write(applescript_code)

    subprocess.run(["osascript", script_path])

def main():
    if len(sys.argv) < 2:
        print("Usage: python script.py <folder>")
        sys.exit(1)

    folder = sys.argv[1]
    sentence_csv = os.path.join(folder, "sentence_level_results.csv")
    word_csv = os.path.join(folder, "word_level_results.csv")

    with open(sentence_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    generate_heatmap_pdf(folder, rows)
    generate_table_pdf(folder, rows, "Sentence Level Data", "sentences.pdf", landscape=True, wide_columns=[1, 2])

    if os.path.isfile(word_csv):
        with open(word_csv, newline="", encoding="utf-8") as f:
            word_rows = list(csv.DictReader(f))
        generate_word_heatmap_pdf(folder, word_rows)
        generate_table_pdf(folder, word_rows, "Word Level Data", "words.pdf")

    merge_pdfs(folder)
    send_email_with_applescript(folder)

if __name__ == "__main__":
    main()