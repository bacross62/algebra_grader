import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_readme_pdf():
    # Paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    readme_path = os.path.join(current_dir, '..', 'README.md')
    output_path = os.path.join(current_dir, '..', 'README.pdf')

    if not os.path.exists(readme_path):
        print(f"Error: README.md not found at {readme_path}")
        return

    # Read Markdown
    with open(readme_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Setup PDF
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='CodeBlock', 
                              parent=styles['Normal'], 
                              fontName='Courier', 
                              fontSize=9, 
                              leading=11, 
                              backColor=colors.lightgrey,
                              borderPadding=5))
    
    story = []
    
    # Simple Markdown Parser
    lines = content.split('\n')
    in_code_block = False
    code_buffer = []

    for line in lines:
        stripped = line.strip()
        
        # Code Blocks
        if stripped.startswith('```'):
            if in_code_block:
                # End of block
                in_code_block = False
                p = Preformatted('\n'.join(code_buffer), styles['CodeBlock'])
                story.append(p)
                story.append(Spacer(1, 10))
                code_buffer = []
            else:
                # Start of block
                in_code_block = True
            continue
            
        if in_code_block:
            code_buffer.append(line)
            continue

        # Headers
        if line.startswith('# '):
            story.append(Paragraph(line[2:], styles['Title']))
            story.append(Spacer(1, 12))
        elif line.startswith('## '):
            story.append(Paragraph(line[3:], styles['Heading2']))
            story.append(Spacer(1, 10))
        elif line.startswith('### '):
            story.append(Paragraph(line[4:], styles['Heading3']))
            story.append(Spacer(1, 8))
        
        # List Items
        elif line.strip().startswith('* ') or line.strip().startswith('- '):
            # Handle bolding in list items
            text = line.strip()[2:]
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            story.append(Paragraph(f"• {text}", styles['Normal']))
            story.append(Spacer(1, 4))
            
        # Normal Text
        elif stripped:
            # Handle bolding
            text = line
            text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
            story.append(Paragraph(text, styles['Normal']))
            story.append(Spacer(1, 6))
        else:
            # Empty line
            story.append(Spacer(1, 6))

    try:
        doc.build(story)
        print(f"Successfully generated README.pdf at {output_path}")
    except Exception as e:
        print(f"Failed to generate PDF: {e}")

if __name__ == "__main__":
    generate_readme_pdf()
