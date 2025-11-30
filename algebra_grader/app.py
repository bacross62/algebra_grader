import os
import glob
import json
import time
import re
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
import logging
import google.generativeai as genai
from docx import Document
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from dotenv import load_dotenv
import subprocess

load_dotenv()
#test to push#
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    filename='grading_errors.log',
    level=logging.ERROR,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def extract_text_from_file(file_storage):
    """
    Extracts text from a FileStorage object (txt, docx, pdf).
    """
    filename = file_storage.filename.lower()
    if filename.endswith('.docx'):
        doc = Document(file_storage)
        return "\n".join([para.text for para in doc.paragraphs])
    elif filename.endswith('.pdf'):
        reader = PdfReader(file_storage)
        return "\n".join([page.extract_text() for page in reader.pages])
    else:
        # Assume text-based
        return file_storage.read().decode('utf-8', errors='ignore')

def clean_json_text(text):
    """
    Cleans the text to ensure it is valid JSON.
    Removes markdown code blocks if present.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

def clean_latex_to_text(text):
    """
    Converts common LaTeX math patterns to readable Unicode text.
    """
    if not text:
        return ""
    
    # Handle fractions first using regex: \frac{a}{b} -> a/b
    # We use a loop to handle nested fractions or multiple fractions
    while r'\frac' in text:
        text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1)/(\2)', text)
        # Break if no more changes to avoid infinite loops in case of malformed latex
        if r'\frac' in text and not re.search(r'\\frac\{([^}]+)\}\{([^}]+)\}', text):
            break

    # Basic replacements
    replacements = {
        r'\times': '×',
        r'\cdot': '·',
        r'\div': '÷',
        r'\pm': '±',
        r'\leq': '≤',
        r'\geq': '≥',
        r'\neq': '≠',
        r'\approx': '≈',
        r'\infty': '∞',
        r'\pi': 'π',
        r'\theta': 'θ',
        r'\alpha': 'α',
        r'\beta': 'β',
        r'\Delta': 'Δ',
        r'\sqrt': '√',
        r'^2': '²',
        r'^3': '³',
        r'^{\circ}': '°',
        r'\circ': '°',
        r'^-1': '^(-1)', # Fix for inverse functions causing black squares
        r'^{-1}': '^(-1)',
        r'⁻¹': '^(-1)', # Handle unicode inverse if AI outputs it
        '$': '', # Remove math delimiters
        '\\': '', # Remove remaining backslashes
        '{': '', # Remove braces
        '}': ''
    }
    
    for latex, unicode_char in replacements.items():
        text = text.replace(latex, unicode_char)
        
    return text

def grade_pdf(pdf_path, rubric_text, api_key):
    """
    Grades a single PDF using Gemini.
    """
    try:
        genai.configure(api_key=api_key)
        
        # Upload the file to Gemini
        sample_file = genai.upload_file(path=pdf_path, display_name=os.path.basename(pdf_path))
        
        # Wait for the file to be active
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = genai.get_file(sample_file.name)

        if sample_file.state.name == "FAILED":
            return {"error": "File processing failed by Gemini", "file": os.path.basename(pdf_path)}

        # Dynamically find a supported model
        available_models = []
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
        except Exception as e:
            print(f"Error listing models: {e}")

        # Priority list of preferred models
        preferred_models = [
            'models/gemini-3-pro-preview',
            'models/gemini-3.0-pro',
            'gemini-3.0-pro',
            'models/gemini-1.5-pro',
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-001',
            'models/gemini-1.5-pro-001',
            'models/gemini-pro-vision', # Fallback for older keys
        ]

        selected_model_name = None
        
        # 1. Try to find a preferred model in the available list
        for pref in preferred_models:
            if pref in available_models:
                selected_model_name = pref
                break
        
        # 2. If no preferred model found, pick the first available 'gemini' model
        if not selected_model_name:
            for m in available_models:
                if 'gemini' in m and 'vision' not in m: # Avoid vision-only legacy if possible, unless 1.5
                     # Actually 1.5 models handle everything. 
                     # Let's just pick the first one that looks like a 1.5 model
                     if '1.5' in m:
                         selected_model_name = m
                         break
        
        # 3. Last resort: just use the first available model or fallback to string
        if not selected_model_name:
             if available_models:
                 selected_model_name = available_models[0]
             else:
                 selected_model_name = 'gemini-1.5-flash' # Blind hope

        print(f"Selected Model: {selected_model_name}")
        model = genai.GenerativeModel(selected_model_name)

        prompt = f"""
        You are an expert Algebra teacher. Your task is to grade the student's quiz submission (attached PDF) based on the provided rubric.
        
        **Rubric:**
        {rubric_text}
        
        **Instructions:**
        1. Analyze the handwritten responses in the PDF.
        2. Grade each question according to the rubric.
        3. **CRITICAL:** Award partial credit for correct steps or logic, even if the final answer is wrong or if the method differs slightly from the rubric but is mathematically valid.
        4. **Feedback Requirement:** For each question, provide a detailed explanation of where exactly points were lost.
        5. **Error Identification:** Explicitly point out any specific incorrect algebra, arithmetic errors, or mathematical misconceptions used by the student.
        6. **Math Formatting:** Do NOT use LaTeX formatting (like \\frac, \\times, $...$). Instead, use standard Unicode mathematical symbols (e.g., Use '1/2' instead of \\frac{{1}}{{2}}, 'x²' instead of x^2, '√' for square root, '×' for multiplication). Make the output plain text readable.
        7. Calculate the total score.
        
        **Output Format:**
        Return the result as a valid JSON object with the following structure:
        {{
            "student_name": "Name found on paper or Filename",
            "quiz_name": "Title of the quiz found on paper or Filename",
            "total_score": <number>,
            "max_score": <number>,
            "questions": [
                {{
                    "question_number": <string>,
                    "score": <number>,
                    "max_points": <number>,
                    "feedback": "<string>",
                    "partial_credit_awarded": <boolean>
                }}
            ],
            "overall_feedback": "<string>"
        }}
        """

        max_retries = 3
        retry_delay = 2 # seconds

        for attempt in range(max_retries):
            try:
                response = model.generate_content([sample_file, prompt], generation_config={"response_mime_type": "application/json"})
                cleaned_text = clean_json_text(response.text)
                return json.loads(cleaned_text)
            except Exception as e:
                if attempt < max_retries - 1:
                    logging.warning(f"Attempt {attempt + 1} failed for {os.path.basename(pdf_path)}: {e}. Retrying...")
                    time.sleep(retry_delay * (attempt + 1)) # Exponential backoff
                else:
                    raise e # Re-raise the last exception if all retries fail

    except Exception as e:
        error_msg = f"Error grading {os.path.basename(pdf_path)}: {str(e)}"
        print(error_msg)
        logging.error(error_msg)
        return {"error": str(e), "file": os.path.basename(pdf_path)}

def generate_feedback_pdf(feedback_data, output_path):
    """
    Generates a PDF feedback report using ReportLab.
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    
    # Register DejaVuSans font
    try:
        font_path = os.path.join(os.path.dirname(__file__), 'static', 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        logging.error(f"Could not register font DejaVuSans: {e}")
        font_name = 'Helvetica' # Fallback

    styles = getSampleStyleSheet()
    # Update styles to use the new font
    styles['Normal'].fontName = font_name
    styles['Heading1'].fontName = font_name
    styles['Heading2'].fontName = font_name
    styles['Heading3'].fontName = font_name
    styles['Title'].fontName = font_name

    story = []

    # Title
    student_name = feedback_data.get('student_name', 'Unknown Student')
    quiz_name = feedback_data.get('quiz_name', 'Quiz')
    title_text = f"{student_name} Feedback {quiz_name}"
    story.append(Paragraph(title_text, styles['Title']))
    story.append(Spacer(1, 12))

    # Score
    total_score = feedback_data.get('total_score', 0)
    max_score = feedback_data.get('max_score', 0)
    score_text = f"<b>Total Score:</b> {total_score} / {max_score}"
    story.append(Paragraph(score_text, styles['Normal']))
    story.append(Spacer(1, 12))

    # Overall Feedback
    overall_feedback = feedback_data.get('overall_feedback', '')
    if overall_feedback:
        story.append(Paragraph("<b>Overall Feedback:</b>", styles['Heading2']))
        story.append(Paragraph(clean_latex_to_text(overall_feedback), styles['Normal']))
        story.append(Spacer(1, 12))

    # Questions
    if 'questions' in feedback_data:
        story.append(Paragraph("<b>Question Details:</b>", styles['Heading2']))
        for q in feedback_data['questions']:
            q_num = q.get('question_number', 'N/A')
            q_score = q.get('score', 0)
            q_max = q.get('max_points', 0)
            q_feedback = q.get('feedback', '')
            partial = q.get('partial_credit_awarded', False)

            q_header = f"<b>Question {q_num}</b> ({q_score}/{q_max})"
            if partial:
                q_header += " <i>(Partial Credit Awarded)</i>"
            
            story.append(Paragraph(q_header, styles['Heading3']))
            story.append(Paragraph(clean_latex_to_text(q_feedback), styles['Normal']))
            story.append(Spacer(1, 6))

    doc.build(story)

def generate_teacher_summary(all_results, output_path, api_key):
    """
    Generates a summary PDF of common misconceptions and errors.
    """
    try:
        logging.info("Generating Teacher Summary...")
        
        # Aggregate all feedback
        aggregated_text = ""
        for res in all_results:
            if "error" in res:
                continue
            aggregated_text += f"\nStudent: {res.get('student_name', 'Unknown')}\n"
            aggregated_text += f"Overall Feedback: {res.get('overall_feedback', '')}\n"
            if 'questions' in res:
                for q in res['questions']:
                    aggregated_text += f"Q{q.get('question_number')}: {q.get('feedback', '')}\n"
        
        if not aggregated_text:
            logging.warning("No feedback data available for summary.")
            return

        # Configure Gemini for summary generation
        genai.configure(api_key=api_key)
        
        # Select model (reuse logic or just pick best available)
        model_name = 'models/gemini-1.5-pro' # Default to a strong model for reasoning
        # Try to find the preferred one if possible, but hardcoding for simplicity in this helper
        # or pass the model object. Let's re-instantiate to be safe.
        
        model = genai.GenerativeModel(model_name) 

        # Get threshold from env
        threshold = float(os.getenv('MISCONCEPTION_THRESHOLD', 0.4))
        threshold_percent = int(threshold * 100)

        prompt = f"""
        Analyze the following feedback provided to algebra students after a quiz.
        Identify the most common misconceptions, frequent procedural errors, and general areas where the class struggled.
        Provide a summary for the teacher with:
        1. **Common Misconceptions**: Identify at least 3 common misconceptions. CRITICAL: Also include ANY other misconception that affects more than {threshold_percent}% of the students.
        2. **Problem Areas**: Which types of questions caused the most trouble?
        3. **Recommendations**: What topics should the teacher review in class?
        
        Format the output as a clean, professional report. Do not use LaTeX. Use Unicode for math symbols.
        
        Feedback Data:
        {aggregated_text[:30000]} # Truncate if too long to avoid token limits
        """
        
        response = model.generate_content(prompt)
        summary_text = response.text
        
        # Generate PDF
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        # Register font if not already (it should be global but let's be safe or just use styles)
        # Assuming DejaVuSans is registered in main scope or we re-register if needed.
        # Since this is a function, we rely on the global registration or fallback.
        font_name = 'DejaVuSans' if 'DejaVuSans' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
        
        styles['Normal'].fontName = font_name
        styles['Heading1'].fontName = font_name
        styles['Heading2'].fontName = font_name
        
        story = []
        story.append(Paragraph("<b>Teacher Summary Report</b>", styles['Title']))
        story.append(Spacer(1, 12))
        
        # Process Markdown-like text from Gemini to Paragraphs
        # Simple split by newlines for now
        for line in summary_text.split('\n'):
            line = line.strip()
            if not line:
                story.append(Spacer(1, 6))
                continue
            
            if line.startswith('**') and line.endswith('**'):
                story.append(Paragraph(clean_latex_to_text(line.replace('**', '')), styles['Heading2']))
            elif line.startswith('* ') or line.startswith('- '):
                story.append(Paragraph(f"• {clean_latex_to_text(line[2:])}", styles['Normal']))
            elif line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. '):
                 story.append(Paragraph(clean_latex_to_text(line), styles['Heading3']))
            else:
                story.append(Paragraph(clean_latex_to_text(line), styles['Normal']))
        
        doc.build(story)
        logging.info(f"Teacher Summary saved to {output_path}")

    except Exception as e:
        logging.error(f"Error generating Teacher Summary: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/grade', methods=['POST'])
def grade():
    # Handle FormData
    api_key = os.getenv('GEMINI_API_KEY')
    folder_path = request.form.get('folder_path')
    rubric_file = request.files.get('rubric_file')

    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"error": "Invalid folder path"}), 400
    if not rubric_file:
        return jsonify({"error": "Rubric file is required"}), 400
    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        return jsonify({"error": "API Key is missing or invalid in .env file"}), 400

    # Extract rubric text
    try:
        rubric_text = extract_text_from_file(rubric_file)
    except Exception as e:
        return jsonify({"error": f"Failed to read rubric file: {str(e)}"}), 400

    pdf_files = glob.glob(os.path.join(folder_path, "*.pdf"))
    
    if not pdf_files:
        return jsonify({"error": "No PDF files found in the specified folder"}), 404

    results = []
    
    # Create feedback folder
    feedback_folder = os.path.join(folder_path, "feedback")
    os.makedirs(feedback_folder, exist_ok=True)

    def generate():
        all_results = [] # Accumulate results for summary
        
        for pdf_file in pdf_files:
            base_name = os.path.basename(pdf_file)
            json_filename = f"{os.path.splitext(base_name)[0]}_result.json"
            json_path = os.path.join(feedback_folder, json_filename)
            
            result = None
            
            # RESUME CAPABILITY: Check if result already exists
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r') as f:
                        result = json.load(f)
                    result['filename'] = base_name # Ensure filename matches
                    logging.info(f"Resuming: Loaded cached result for {base_name}")
                except Exception as e:
                    logging.error(f"Error loading cached result for {base_name}: {e}")
            
            # If not found or error loading, grade it
            if not result:
                result = grade_pdf(pdf_file, rubric_text, api_key)
                result['filename'] = base_name
                
                # Save result for future resumption
                if "error" not in result:
                    try:
                        with open(json_path, 'w') as f:
                            json.dump(result, f, indent=4)
                    except Exception as e:
                        logging.error(f"Error saving result cache for {base_name}: {e}")
            
            # Generate Feedback PDF
            if "error" not in result:
                try:
                    student_name = result.get('student_name', 'Student').replace('/', '-')
                    quiz_name = result.get('quiz_name', 'Quiz').replace('/', '-')
                    pdf_filename = f"{student_name} Feedback {quiz_name}.pdf"
                    output_path = os.path.join(feedback_folder, pdf_filename)
                    
                    # Only generate PDF if it doesn't exist (speed up resume)
                    if not os.path.exists(output_path):
                        generate_feedback_pdf(result, output_path)
                except Exception as e:
                    error_msg = f"Error generating PDF for {pdf_file}: {e}"
                    print(error_msg)
                    logging.error(error_msg)
                    result['pdf_error'] = str(e)
            
            # Yield result as JSON line
            yield json.dumps(result) + '\n'
            
            # Add to accumulation list
            all_results.append(result)

        # Generate Teacher Summary after all quizzes are processed
        try:
            summary_path = os.path.join(feedback_folder, "Teacher_Summary.pdf")
            generate_teacher_summary(all_results, summary_path, api_key)
            # Optional: Yield a special event or log indicating summary is ready
            # yield json.dumps({"info": "Teacher Summary Generated"}) + '\n'
        except Exception as e:
            logging.error(f"Failed to trigger teacher summary: {e}")

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

@app.route('/select_folder')
def select_folder():
    """
    Opens a system dialog to select a folder using AppleScript (macOS native).
    """
    try:
        # AppleScript command to choose a folder
        script = 'POSIX path of (choose folder with prompt "Select the Quiz Folder")'
        
        # Run the script using osascript
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
        
        if result.returncode == 0:
            folder_path = result.stdout.strip()
            return jsonify({"path": folder_path})
        else:
            # User cancelled or error
            return jsonify({"path": ""}) 
            
    except Exception as e:
        logging.error(f"Error selecting folder: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
