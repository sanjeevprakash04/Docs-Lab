import os
import uuid
import zipfile
from flask import url_for
from lxml import etree
from docx import Document

TEMP_IMAGE_DIR = 'static/temp_images'

def clear_temp_images():
    if os.path.exists(TEMP_IMAGE_DIR):
        for file in os.listdir(TEMP_IMAGE_DIR):
            file_path = os.path.join(TEMP_IMAGE_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(TEMP_IMAGE_DIR)

def docx_to_html(path):
    try:
        doc = Document(path)
        html = ""
        toc = []
        heading_counter = 0
        img_index = 0

        with zipfile.ZipFile(path, 'r') as docx_zip:
            rels = {}
            rels_path = 'word/_rels/document.xml.rels'
            if rels_path in docx_zip.namelist():
                rel_tree = etree.fromstring(docx_zip.read(rels_path))
                for rel in rel_tree.xpath('//rel:Relationship', namespaces={
                    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'
                }):
                    rId = rel.get('Id')
                    target = rel.get('Target')
                    if rId and target:
                        zip_target_path = f'word/{target}'
                        if zip_target_path in docx_zip.namelist():
                            rels[rId] = docx_zip.read(zip_target_path)

        for para in doc.paragraphs:
            style = para.style.name.lower()
            text = para.text.strip()
            align = para.alignment
            align_style = ""
            if align == 1:
                align_style = 'text-align:center;'
            elif align == 2:
                align_style = 'text-align:right;'
            elif align == 3:
                align_style = 'text-align:justify;'

            heading_tag = None
            anchor_id = ""

            if "heading 1" in style:
                heading_tag = "h1"
            elif "heading 2" in style:
                heading_tag = "h2"
            elif "heading 3" in style:
                heading_tag = "h3"

            if heading_tag:
                anchor_id = f"heading-{heading_counter}"
                heading_counter += 1
                toc.append(f'<li><a href="#{anchor_id}">{text}</a></li>')
                html += f'<{heading_tag} id="{anchor_id}" style="{align_style}">'
            else:
                html += f'<p style="{align_style}">'

            for run in para.runs:
                run_text = run.text.replace('\n', '<br>')

                # Image check
                if 'graphic' in run._element.xml:
                    element_tree = etree.fromstring(run._element.xml.encode())
                    blips = element_tree.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
                    if blips:
                        rEmbed = blips[0].get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                        if rEmbed and rEmbed in rels:
                            image_data = rels[rEmbed]
                            image_name = f"{uuid.uuid4()}.png"
                            image_path = os.path.join(TEMP_IMAGE_DIR, image_name)
                            with open(image_path, "wb") as f:
                                f.write(image_data)
                            img_url = url_for('static', filename=f"temp_images/{image_name}")
                            html += f'''
                            <div style="margin-left: 8rem; width: 60%;">
                                <img src="{img_url}" alt="Image" class="clickable-image" style="max-width: 500px; max-height: 400px; object-fit: contain; cursor: pointer;" />
                            </div>
                            '''
                    continue

                style_start = ""
                style_end = ""

                if run.bold:
                    style_start += "<strong>"
                    style_end = "</strong>" + style_end
                if run.italic:
                    style_start += "<em>"
                    style_end = "</em>" + style_end
                if run.underline:
                    style_start += "<u>"
                    style_end = "</u>" + style_end

                html += f"{style_start}{run_text}{style_end}"

            if heading_tag:
                html += f"</{heading_tag}>"
            else:
                html += "</p>"

        toc_html = "<ul class='toc-list'>" + "".join(toc) + "</ul>"
        return html, toc_html
    except Exception as e:
        return f"<p>Error reading document: {str(e)}</p>", ""

