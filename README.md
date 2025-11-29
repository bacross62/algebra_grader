# Algebra Grader

Automated grading tool for algebra quizzes using Google's Gemini AI.

## Features
- **PDF Grading**: Automatically extracts and grades handwritten student responses from PDF files.
- **Partial Credit**: AI-powered logic awards partial credit for correct steps even if the final answer is wrong.
- **Feedback Generation**: Generates detailed feedback PDFs for each student, including score breakdowns and specific comments.
- **Web Interface**: Simple browser-based interface for uploading quizzes and rubrics.

## Requirements
- Python 3.9+
- Google Gemini API Key

## Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/bacross62/algebra_grader.git
   cd algebra_grader
   ```

2. **Install Dependencies**
   It is recommended to use a virtual environment.
   ```bash
   pip install -r algebra_grader/requirements.txt
   ```

3. **Environment Configuration**
   Create a `.env` file in the `algebra_grader` directory:
   ```bash
   GEMINI_API_KEY=your_api_key_here
   ```

## Usage

1. **Start the Application**
   ```bash
   cd algebra_grader
   python app.py
   ```

2. **Grade Quizzes**
   - Open your browser to `http://127.0.0.1:5001`.
   - Upload the folder containing student PDF quizzes.
   - Upload the grading rubric (text or file).
   - Click "Grade".

3. **View Results**
   - The application will display the results on the screen.
   - Feedback PDFs will be generated in a `feedback` subfolder within your quizzes directory.
