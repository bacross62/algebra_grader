import os
import glob
import json
import time
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
from docx import Document
from pypdf import PdfReader
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from dotenv import load_dotenv

load_dotenv()
#test to push#
app = Flask(__name__)


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
            'models/gemini-1.5-flash',
            'models/gemini-1.5-pro',
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
        6. Calculate the total score.
        
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

        response = model.generate_content([sample_file, prompt], generation_config={"response_mime_type": "application/json"})
        
        return json.loads(response.text)

    except Exception as e:
        return {"error": str(e), "file": os.path.basename(pdf_path)}

def generate_feedback_pdf(feedback_data, output_path):
    """
    Generates a PDF feedback report using ReportLab.
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
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
        story.append(Paragraph(overall_feedback, styles['Normal']))
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
            story.append(Paragraph(q_feedback, styles['Normal']))
            story.append(Spacer(1, 6))

    doc.build(story)

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

    for pdf_file in pdf_files:
        result = grade_pdf(pdf_file, rubric_text, api_key)
        result['filename'] = os.path.basename(pdf_file)
        results.append(result)

        # Generate Feedback PDF
        if "error" not in result:
            try:
                student_name = result.get('student_name', 'Student').replace('/', '-')
                quiz_name = result.get('quiz_name', 'Quiz').replace('/', '-')
                pdf_filename = f"{student_name} Feedback {quiz_name}.pdf"
                output_path = os.path.join(feedback_folder, pdf_filename)
                generate_feedback_pdf(result, output_path)
            except Exception as e:
                print(f"Error generating PDF for {pdf_file}: {e}")
                result['pdf_error'] = str(e)

    return jsonify({"results": results})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
