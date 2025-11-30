document.addEventListener('DOMContentLoaded', () => {
    const gradingForm = document.getElementById('gradingForm');
    const gradeBtn = document.getElementById('gradeBtn');
    const btnText = gradeBtn.querySelector('.btn-text');
    const loader = gradeBtn.querySelector('.loader');
    const resultsSection = document.getElementById('resultsSection');
    const resultsGrid = document.getElementById('resultsGrid');
    const processedCount = document.getElementById('processedCount');
    const avgScore = document.getElementById('avgScore');
    const selectFolderBtn = document.getElementById('selectFolderBtn');
    const folderPathInput = document.getElementById('folderPath');

    selectFolderBtn.addEventListener('click', async () => {
        try {
            const response = await fetch('/select_folder');
            const data = await response.json();

            if (data.path) {
                folderPathInput.value = data.path;
            }
        } catch (error) {
            console.error('Error selecting folder:', error);
            alert('Failed to open folder selector.');
        }
    });

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
        processedCount.textContent = '0';
        avgScore.textContent = '0%';
        totalPercentageSum = 0;
        validScoreCount = 0;

        // Wake Lock to prevent sleep
        let wakeLock = null;
        try {
            if ('wakeLock' in navigator) {
                wakeLock = await navigator.wakeLock.request('screen');
                console.log('Wake Lock is active');
            }
        } catch (err) {
            console.error(`Wake Lock error: ${err.name}, ${err.message}`);
        }

        try {
            const formData = new FormData();
            // API Key is handled by backend from .env
            formData.append('folder_path', folderPath);
            formData.append('rubric_file', rubricFile);

            const response = await fetch('/grade', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'An error occurred during grading');
            }

            resultsSection.classList.remove('hidden');

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');

                // Process all complete lines
                buffer = lines.pop(); // Keep the last incomplete line in buffer

                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const result = JSON.parse(line);
                            appendResult(result);
                        } catch (e) {
                            console.error('Error parsing JSON line:', e);
                        }
                    }
                }
            }

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            // Release Wake Lock
            if (wakeLock !== null) {
                wakeLock.release()
                    .then(() => {
                        wakeLock = null;
                        console.log('Wake Lock released');
                    });
            }

            // Reset UI
            gradeBtn.disabled = false;
            btnText.textContent = 'Start Grading';
            loader.classList.add('hidden');
        }
    });

    function appendResult(result) {
        // Update stats
        const currentCount = parseInt(processedCount.textContent) + 1;
        processedCount.textContent = currentCount;

        if (!result.error) {
            const percentage = (result.total_score / result.max_score) * 100;

            // Update average
            // Note: This is a simple running average approximation for UI display
            // For exact average we'd need to track total points and total max points
            let currentAvgStr = avgScore.textContent.replace('%', '');
            let currentAvg = currentAvgStr === '0' || currentAvgStr === 'N/A' ? 0 : parseInt(currentAvgStr);

            // If it's the first valid score
            if (currentAvg === 0 && currentCount === 1) {
                avgScore.textContent = Math.round(percentage) + '%';
            } else {
                // Re-calculate average based on displayed value (simplified)
                // Better approach: store totals in variables outside
                // But for now, let's just do a simple update or keep track of totals globally
            }
        }

        if (result.error) {
            renderErrorCard(result);
            return;
        }

        const percentage = (result.total_score / result.max_score) * 100;

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

        // Update average properly
        updateAverage(percentage);
    }

    let totalPercentageSum = 0;
    let validScoreCount = 0;

    function updateAverage(newPercentage) {
        totalPercentageSum += newPercentage;
        validScoreCount++;
        avgScore.textContent = Math.round(totalPercentageSum / validScoreCount) + '%';
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
