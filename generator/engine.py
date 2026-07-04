# Note: You must run `pip install pymupdf` to enable the hyperlink embedding phase.
import os
import random
import json
import re
import sys
from urllib.parse import unquote
from PIL import Image, ImageDraw, ImageFont

def generate_name_pdf(target_name, base_folder="nasa_alphabet_database", output_folder="."):
    target_name = target_name.upper().replace(" ", "")
    print(f"\n--- Booting Engine for '{target_name}' ---")

    # UPDATED: Look for metadata.json in the root directory where the script runs
    metadata_file = "metadata.json"
    if not os.path.exists(metadata_file):
        print(f"Error: {metadata_file} not found. Did you run the scraper?")
        return False
        
    with open(metadata_file, "r", encoding="utf-8") as f:
        raw_db = json.load(f)
        
        master_db = {}
        for k, v in raw_db.items():
            k_lower = k.lower()
            master_db[k_lower] = v
            
            prefix_match = re.match(r'^([a-z])[_\-](\d+)', k_lower)
            if prefix_match:
                prefix_key = f"{prefix_match.group(1)}-{prefix_match.group(2)}"
                master_db[prefix_key] = v
                
            clean_k = re.sub(r'[^a-z0-9]', '', k_lower)
            master_db[clean_k] = v

    image_pools = {}
    for letter in set(target_name):
        folder_path = os.path.join(base_folder, letter)
        images = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        image_pools[letter] = {'unused': images, 'used': []}

    def has_unused():
        return any(len(image_pools[l]['unused']) > 0 for l in set(target_name))

    spellings = []
    while has_unused():
        current_spelling = []
        for letter in target_name:
            pool = image_pools[letter]
            if pool['unused']:
                path = pool['unused'].pop(0)
                pool['used'].append(path)
            else:
                path = random.choice(pool['used']) 
            current_spelling.append((letter, path))
        spellings.append(current_spelling)

    canvas_w, canvas_h = 3500, 4950
    margin = 200
    strips_per_page = 5
    gap_size = 100
    
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 24)
        font_data = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font_title = ImageFont.load_default()
        font_data = ImageFont.load_default()

    def wrap_text(text, font, max_width, draw):
        words = text.split()
        lines, current_line = [], []
        for word in words:
            test_line = ' '.join(current_line + [word])
            if draw.textbbox((0, 0), test_line, font=font)[2] <= max_width:
                current_line.append(word)
            else:
                if not current_line: lines.append(word)
                else:
                    lines.append(' '.join(current_line))
                    current_line = [word]
        if current_line: lines.append(' '.join(current_line))
        return '\n'.join(lines)

    pdf_pages = []
    all_page_links = []
    chunks = [spellings[i:i + strips_per_page] for i in range(0, len(spellings), strips_per_page)]

    temp_img = Image.new('RGB', (1, 1))
    temp_draw = ImageDraw.Draw(temp_img)

    for chunk in chunks:
        strip_data = [] 
        for spelling in chunk:
            images_in_strip = []
            for letter, path in spelling:
                img = Image.open(path).convert("RGB")
                ratio = img.width / img.height
                
                filename_no_ext = os.path.splitext(os.path.basename(path))[0].lower()
                filename_no_ext = unquote(filename_no_ext) 
                
                meta = master_db.get(filename_no_ext)
                if not meta:
                    clean_file = re.sub(r'[^a-z0-9]', '', filename_no_ext)
                    meta = master_db.get(clean_file)
                    
                if not meta:
                    prefix_match = re.match(r'^([a-z])[_\-](\d+)', filename_no_ext)
                    if prefix_match:
                        prefix_key = f"{prefix_match.group(1)}-{prefix_match.group(2)}"
                        meta = master_db.get(prefix_key, {})
                    else:
                        meta = {}
                
                images_in_strip.append({
                    "img": img, 
                    "ratio": ratio, 
                    "location": meta.get("location", "Unknown Location"),
                    "date": meta.get("date", "Date Unknown"),
                    "coords": meta.get("coords", "Coords Unknown"),
                    "url": meta.get("detail_url", "")
                })
            strip_data.append(images_in_strip)

        available_w = canvas_w - (margin * 2)
        available_h = canvas_h - (margin * 2)
        target_width = available_w

        strip_dynamic_heights = [0] * len(strip_data)

        for s_idx, strip in enumerate(strip_data):
            H = int(target_width / sum(item["ratio"] for item in strip))
            current_x = (canvas_w - target_width) / 2
            max_strip_text_height = 0
            
            for i, item in enumerate(strip):
                new_w = int(H * item["ratio"])
                if i == len(strip) - 1:
                    new_w = int(target_width - (current_x - (canvas_w - target_width)/2))
                
                max_text_width = new_w - 20 
                wrapped_loc = wrap_text(item["location"], font_title, max_text_width, temp_draw)
                wrapped_date = wrap_text(item["date"], font_data, max_text_width, temp_draw)
                
                loc_bbox = temp_draw.multiline_textbbox((0, 0), wrapped_loc, font=font_title, anchor="ma", align="center")
                date_bbox = temp_draw.multiline_textbbox((0, 0), wrapped_date, font=font_data, anchor="ma", align="center")
                coords_bbox = temp_draw.multiline_textbbox((0, 0), item["coords"], font=font_data, anchor="ma", align="center")
                
                loc_h = loc_bbox[3] - loc_bbox[1]
                date_h = date_bbox[3] - date_bbox[1]
                coords_h = coords_bbox[3] - coords_bbox[1]
                
                total_text_h = loc_h + 15 + date_h + 15 + coords_h + 20
                if total_text_h > max_strip_text_height:
                    max_strip_text_height = total_text_h
                
                current_x += new_w
            
            strip_dynamic_heights[s_idx] = max_strip_text_height

        image_only_h = sum((target_width / sum(item["ratio"] for item in strip)) for strip in strip_data)
        total_dynamic_text_space = sum(strip_dynamic_heights)
        fixed_vertical_space = total_dynamic_text_space + (gap_size * max(0, len(chunk) - 1))
        available_image_h = available_h - fixed_vertical_space

        if image_only_h > available_image_h:
            target_width *= (available_image_h / image_only_h)

        page = Image.new('RGB', (canvas_w, canvas_h), 'white')
        draw = ImageDraw.Draw(page)
        
        current_page_links = []
        pdf_dpi = 300.0
        points_per_inch = 72.0
        scale = points_per_inch / pdf_dpi

        for s_idx, strip in enumerate(strip_data):
            H = int(target_width / sum(item["ratio"] for item in strip))
            current_x = (canvas_w - target_width) / 2
            max_strip_text_height = 0
            
            for i, item in enumerate(strip):
                new_w = int(H * item["ratio"])
                if i == len(strip) - 1:
                    new_w = int(target_width - (current_x - (canvas_w - target_width)/2))
                
                max_text_width = new_w - 20 
                wrapped_loc = wrap_text(item["location"], font_title, max_text_width, draw)
                wrapped_date = wrap_text(item["date"], font_data, max_text_width, draw)
                
                loc_bbox = draw.multiline_textbbox((0, 0), wrapped_loc, font=font_title, anchor="ma", align="center")
                date_bbox = draw.multiline_textbbox((0, 0), wrapped_date, font=font_data, anchor="ma", align="center")
                coords_bbox = draw.multiline_textbbox((0, 0), item["coords"], font=font_data, anchor="ma", align="center")
                
                total_text_h = (loc_bbox[3] - loc_bbox[1]) + 15 + (date_bbox[3] - date_bbox[1]) + 15 + (coords_bbox[3] - coords_bbox[1]) + 20
                if total_text_h > max_strip_text_height:
                    max_strip_text_height = total_text_h
                    
                current_x += new_w
                
            strip_dynamic_heights[s_idx] = max_strip_text_height

        actual_total_h = sum((target_width / sum(item["ratio"] for item in strip)) + strip_dynamic_heights[s_idx] for s_idx, strip in enumerate(strip_data))
        actual_total_h += gap_size * max(0, len(chunk) - 1)
        current_y = (canvas_h - actual_total_h) / 2

        for s_idx, strip in enumerate(strip_data):
            H = int(target_width / sum(item["ratio"] for item in strip))
            current_x = (canvas_w - target_width) / 2 

            for i, item in enumerate(strip):
                new_w = int(H * item["ratio"])
                if i == len(strip) - 1:
                    new_w = int(target_width - (current_x - (canvas_w - target_width)/2))

                resized = item["img"].resize((new_w, H), Image.Resampling.LANCZOS)
                page.paste(resized, (int(current_x), int(current_y)))

                max_text_width = new_w - 20 
                wrapped_loc = wrap_text(item["location"], font_title, max_text_width, draw)
                wrapped_date = wrap_text(item["date"], font_data, max_text_width, draw)
                
                center_x = current_x + (new_w / 2)
                text_y = current_y + H + 20
                
                draw.multiline_text((center_x, text_y), wrapped_loc, fill="black", font=font_title, anchor="ma", align="center")
                loc_bbox = draw.multiline_textbbox((center_x, text_y), wrapped_loc, font=font_title, anchor="ma", align="center")
                text_y = loc_bbox[3] + 15 
                
                draw.multiline_text((center_x, text_y), wrapped_date, fill="#444444", font=font_data, anchor="ma", align="center")
                date_bbox = draw.multiline_textbbox((center_x, text_y), wrapped_date, font=font_data, anchor="ma", align="center")
                text_y = date_bbox[3] + 15
                
                # Draw coordinates in blue to indicate they are hyperlinks
                link_color = "blue" if item["url"] else "#444444"
                draw.multiline_text((center_x, text_y), item["coords"], fill=link_color, font=font_data, anchor="ma", align="center")
                coords_bbox = draw.multiline_textbbox((center_x, text_y), item["coords"], font=font_data, anchor="ma", align="center")

                if item["url"]:
                    pad = 10
                    rect = [
                        (coords_bbox[0] - pad) * scale, 
                        (coords_bbox[1] - pad) * scale, 
                        (coords_bbox[2] + pad) * scale, 
                        (coords_bbox[3] + pad) * scale
                    ]
                    current_page_links.append({"rect": rect, "url": item["url"]})

                current_x += new_w

            current_y += (H + strip_dynamic_heights[s_idx] + gap_size)

        pdf_pages.append(page)
        all_page_links.append(current_page_links)

    output_filename = os.path.join(output_folder, f"{target_name}_Generated.pdf")
    if pdf_pages:
        # Phase 1: Save standard image PDF
        pdf_pages[0].save(output_filename, "PDF", resolution=300.0, save_all=True, append_images=pdf_pages[1:])
        
        # Phase 2: Inject clickable hyperlinks using PyMuPDF
        try:
            import fitz 
            doc = fitz.open(output_filename)
            for page_idx, links in enumerate(all_page_links):
                pdf_page = doc[page_idx]
                for link in links:
                    pdf_page.insert_link({
                        "kind": fitz.LINK_URI, 
                        "from": fitz.Rect(link["rect"]), 
                        "uri": link["url"]
                    })
            
            temp_filename = output_filename + ".tmp.pdf"
            doc.save(temp_filename)
            doc.close()
            os.replace(temp_filename, output_filename)
            print(f"Success! Saved to {output_filename} with active map hyperlinks.")
            
        except ImportError:
            print(f"Success! Saved to {output_filename}.")
            print("\nNotice: Clickable hyperlinks were skipped. To enable map embedding, you must run: pip install pymupdf")
            
        return True

if __name__ == "__main__":
    import sys
    
    # Check if a name was passed as a command-line argument
    if len(sys.argv) > 1:
        user_name = " ".join(sys.argv[1:])
    else:
        # If not, prompt the user to type it in interactively
        user_name = input("Enter the name you want to generate a poster for: ")
        
    if user_name.strip():
        generate_name_pdf(user_name.strip())
    else:
        print("Error: No name provided. Exiting.")