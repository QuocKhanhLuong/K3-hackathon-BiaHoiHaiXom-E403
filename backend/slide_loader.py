"""
Dynamic Slide Loader for VLearn Tutor
Reads actual PDF slides from data/vlearn-pack/slides/
"""
import os
import fitz

SLIDES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/vlearn-pack/slides"))

def load_pdf_slides():
    pdf_files = [
        {"deck_id": "d1", "filename": "d1-slide-hackathon.pdf", "title_prefix": "Day 1: AI & LLM Foundation"},
        {"deck_id": "d2", "filename": "d2-slide-hackathon.pdf", "title_prefix": "Day 2: Xác định bài toán cho AI"}
    ]

    all_slides = []
    global_page_counter = 1

    for item in pdf_files:
        pdf_path = os.path.join(SLIDES_DIR, item["filename"])
        if not os.path.exists(pdf_path):
            continue

        try:
            doc = fitz.open(pdf_path)
            for i, page in enumerate(doc):
                raw_text = page.get_text().strip()
                lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

                # Title extraction logic
                title = item["title_prefix"]
                subtitle = f"{item['filename']} · Page {i+1}"
                
                if lines:
                    # Skip common header line if present
                    first_line = lines[0]
                    if ("AI IN ACTION" in first_line or "DAY" in first_line) and len(lines) > 1:
                        title = lines[1]
                        if len(lines) > 2:
                            subtitle = lines[2]
                    else:
                        title = first_line
                        if len(lines) > 1:
                            subtitle = lines[1]

                # Format content as HTML paragraphs
                body_lines = lines[1:8] if len(lines) > 1 else lines
                formatted_content = "".join([f"<p>{line}</p>" for line in body_lines])

                all_slides.append({
                    "page": global_page_counter,
                    "deck_id": item["deck_id"],
                    "deck_name": item["title_prefix"],
                    "page_in_deck": i + 1,
                    "title": title,
                    "subtitle": subtitle,
                    "content": formatted_content,
                    "raw_text": raw_text,
                    "code": f"{item['filename']}#page={i+1}"
                })
                global_page_counter += 1
        except Exception as e:
            print(f"[Slide Loader] Warning loading {item['filename']}: {e}")

    return all_slides

# Preload slides
ALL_PDF_SLIDES = load_pdf_slides()
