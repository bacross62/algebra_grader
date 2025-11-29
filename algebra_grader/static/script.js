document.addEventListener('DOMContentLoaded', () => {
    const gradingForm = document.getElementById('gradingForm');
    const gradeBtn = document.getElementById('gradeBtn');
    const btnText = gradeBtn.querySelector('.btn-text');
    const loader = gradeBtn.querySelector('.loader');
    const resultsSection = document.getElementById('resultsSection');
    const resultsGrid = document.getElementById('resultsGrid');
    const processedCount = document.getElementById('processedCount');
    const avgScore = document.getElementById('avgScore');

    gradingForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const folderPath = document.getElementById('folderPath').value;
        const rubricFile = document.getElementById('rubricFile').files[0];

        if (!rubricFile) {
            alert("Please upload a rubric file.");
            return;
        }

        // UI Loading State
        gradeBtn.disabled = true;
        btnText.textContent = 'Grading in progress...';
        loader.classList.remove('hidden');
        resultsSection.classList.add('hidden');
        resultsGrid.innerHTML = '';

        try {
            const formData = new FormData();
            // API Key is handled by backend from .env
            formData.append('folder_path', folderPath);
            formData.append('rubric_file', rubricFile);

            const response = await fetch('/grade', {
                method: 'POST',
                body: formData, // Fetch automatically sets Content-Type to multipart/form-data
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'An error occurred during grading');
            }

            renderResults(data.results);

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            // Reset UI
            gradeBtn.disabled = false;
            btnText.textContent = 'Start Grading';
            loader.classList.add('hidden');
        }
    });

    function renderResults(results) {
        resultsSection.classList.remove('hidden');
        processedCount.textContent = results.length;

        let totalPercentage = 0;
        let validScores = 0;

        results.forEach(result => {
            if (result.error) {
                renderErrorCard(result);
                return;
            }

            const percentage = (result.total_score / result.max_score) * 100;
            totalPercentage += percentage;
            validScores++;

            const card = document.createElement('div');
            card.className = 'result-card glass-card';

            let questionsHtml = '';
            if (result.questions) {
                questionsHtml = result.questions.map(q => `
                    <div class="question-item">
                        <div class="q-header">
                            <span class="q-number">Q${q.question_number}</span>
                            <span class="q-score">${q.score}/${q.max_points}</span>
                        </div>
                        <div class="q-feedback">
                            ${q.feedback}
                            ${q.partial_credit_awarded ? '<span class="partial-badge">Partial Credit</span>' : ''}
                        </div>
                    </div>
                `).join('');
            }

            card.innerHTML = `
                <div class="result-header">
                    <div>
                        <div class="student-name">${result.student_name || result.filename}</div>
                        <div class="filename" style="font-size: 0.8rem; color: var(--text-secondary);">${result.filename}</div>
                    </div>
                    <div>
                        <div class="total-score">${result.total_score}/${result.max_score}</div>
                        <span class="score-label">${Math.round(percentage)}%</span>
                    </div>
                </div>
                <div class="questions-list">
                    ${questionsHtml}
                </div>
                <div class="overall-feedback">
                    "${result.overall_feedback || 'No feedback provided.'}"
                </div>
            `;

            resultsGrid.appendChild(card);
        });

        if (validScores > 0) {
            avgScore.textContent = Math.round(totalPercentage / validScores) + '%';
        } else {
            avgScore.textContent = 'N/A';
        }
    }

    function renderErrorCard(result) {
        const card = document.createElement('div');
        card.className = 'result-card glass-card';
        card.style.border = '1px solid #ef4444';

        card.innerHTML = `
            <div class="result-header">
                <div class="student-name" style="color: #ef4444;">Error</div>
            </div>
            <p style="color: var(--text-secondary);">${result.file}</p>
            <p style="color: #fca5a5;">${result.error}</p>
        `;
        resultsGrid.appendChild(card);
    }
});
