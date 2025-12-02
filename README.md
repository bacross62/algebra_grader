# Algebra Grader AI

A robust, AI-powered tool for automatically grading handwritten algebra quizzes. It uses Google's Gemini models to analyze student work, award partial credit, and generate detailed feedback reports.

## Features

*   **AI-Powered Grading**: Uses Gemini 3 Pro (and fallbacks) to understand handwritten math and logic.
*   **Partial Credit**: Awards points for correct steps even if the final answer is wrong.
*   **Detailed Feedback**: Generates a PDF for each student explaining their mistakes.
*   **Teacher Summary**: Creates a class-wide report identifying common misconceptions and problem areas.
*   **Anti-Cheating**: Analyzes student reasoning across the class to detect suspicious similarities and potential copying.
*   **Privacy Focused**: Optional "Privacy Mode" suppresses detailed logging to ensure student data remains ephemeral.
*   **Resume Capability**: Automatically skips already graded quizzes if interrupted, saving time and API credits.
*   **Streaming Responses**: Shows grading progress in real-time to prevent browser timeouts.
*   **Robustness**: Handles API timeouts with retries and prevents computer sleep during grading (Wake Lock).
*   **Math Rendering**: Cleanly renders mathematical symbols (fractions, exponents, roots) using Unicode.
*   **Customizable**: Configurable rubric and misconception thresholds.
*   **Fairfield Prep Theme**: Designed with the school's official colors.

## Requirements

*   Python 3.10+
*   Google Gemini API Key

## Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd algebra_grader
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Create a `.env` file in the `algebra_grader` directory with your API key and settings.

    **Sample `.env` file:**
    ```env
    # Your Google Gemini API Key
    GEMINI_API_KEY=your_actual_api_key_here

    # Threshold for including misconceptions in the Teacher Summary (0.4 = 40%)
    MISCONCEPTION_THRESHOLD=0.4
    ```

## Usage

1.  **Start the application**:
    ```bash
    python app.py
    ```

2.  **Open in Browser**:
    Go to `http://127.0.0.1:5001`.

3.  **Grade Quizzes**:
    *   **Select Folder**: Click the button to choose the folder containing your student PDF quizzes.
    *   **Upload Rubric**: Select your grading rubric file (Text, Markdown, PDF, or Word).
    *   **Privacy & Cheating**:
        *   **Privacy Mode**: Checked by default. Prevents saving work for training and suppresses local data logging.
        *   **Anti-Cheating**: Checked by default. Enables cross-student analysis to detect copying.
    *   **Start**: Click "Start Grading".

4.  **View Results**:
    *   Watch the progress in real-time.
    *   Find individual feedback PDFs in a `feedback` subfolder within your quiz directory.
    *   Find the `Teacher_Summary.pdf` in the same `feedback` folder after grading completes.

## License

MIT License

## Built With

*   **Google Gemini 3 Pro**: Advanced multimodal AI model for reasoning and grading.
*   **Antigravity**: Agentic AI coding assistant by Google DeepMind.
