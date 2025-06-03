// static/js/quiz.js
document.addEventListener('DOMContentLoaded', function() {
    const questionDiv = document.querySelector('.quiz-question');
    if (!questionDiv) return; // যদি কুইজ প্রশ্ন না থাকে, তাহলে কিছুই করবেন না

    const optionButtons = questionDiv.querySelectorAll('.option-button');
    const feedbackDiv = questionDiv.querySelector('.feedback');
    const nextQuestionForm = document.getElementById('next-question-form');
    const loadingText = document.getElementById('loading-text');

    const scoreSpan = document.getElementById('current-score');

    const questionId = parseInt(questionDiv.dataset.questionId);
    const serverCorrectOptionKey = questionDiv.dataset.correctOption;
    const isAlreadyAnsweredOnLoad = questionDiv.dataset.answered === 'true';
    const userChoiceOnLoad = questionDiv.dataset.userChoice;
    // const isCorrectOnLoad = questionDiv.dataset.isCorrectAnswer === 'true'; // This can be derived

    function applyAnswerStyles(selectedKey, actualCorrectKey, isUserCorrect) {
        optionButtons.forEach(btn => {
            btn.disabled = true;
            const optionKey = btn.dataset.option;

            if (optionKey === selectedKey) { // ব্যবহারকারীর নির্বাচিত অপশন
                if (isUserCorrect) {
                    btn.classList.add('correct');
                } else {
                    btn.classList.add('incorrect');
                }
            }
            // সঠিক উত্তরটি সবসময় সবুজ করুন, যদি ব্যবহারকারীর উত্তর ভুল হয় বা সঠিক উত্তর এটিই হয়
            if (optionKey === actualCorrectKey) {
                if (!btn.classList.contains('correct')) { // যদি ইতিমধ্যে সবুজ না হয়ে থাকে
                    btn.classList.add('correct');
                }
            }
        });
        if (nextQuestionForm) {
            nextQuestionForm.style.display = 'block';
        }
    }

    // পৃষ্ঠা লোড হওয়ার সময় যদি প্রশ্নের উত্তর আগে দেওয়া থাকে
    if (isAlreadyAnsweredOnLoad && userChoiceOnLoad) {
        const wasUserCorrectOnLoad = userChoiceOnLoad === serverCorrectOptionKey;
        applyAnswerStyles(userChoiceOnLoad, serverCorrectOptionKey, wasUserCorrectOnLoad);

        if (wasUserCorrectOnLoad) {
            feedbackDiv.textContent = 'আপনি এই প্রশ্নের সঠিক উত্তর দিয়েছিলেন।';
            feedbackDiv.className = 'feedback feedback-correct'; // ক্লাস যোগ
        } else {
            feedbackDiv.textContent = 'আপনি এই প্রশ্নের ভুল উত্তর দিয়েছিলেন। সঠিক উত্তরটি সবুজ করা হয়েছে।';
            feedbackDiv.className = 'feedback feedback-incorrect'; // ক্লাস যোগ
        }
    }


    optionButtons.forEach(button => {
        button.addEventListener('click', function() {
            // যদি বাটনগুলো আগে থেকেই ডিজেবল থাকে (যেমন, উত্তর দেওয়া হয়ে গেছে), তাহলে কিছু করবেন না
            if (this.disabled) {
                return;
            }

            const selectedOptionKey = this.dataset.option;

            // ক্লিক করার সাথে সাথেই সব বাটন ডিজেবল করুন
            optionButtons.forEach(btn => btn.disabled = true);
            if(loadingText) loadingText.style.display = 'block';
            if(feedbackDiv) feedbackDiv.textContent = ''; // আগের ফিডব্যাক মুছে ফেলুন

            fetch('/submit_answer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json' // সার্ভার থেকে JSON আশা করছি
                },
                body: JSON.stringify({
                    question_id: questionId,
                    answer: selectedOptionKey
                })
            })
            .then(response => {
                if (!response.ok) {
                    // সার্ভার থেকে একটি ত্রুটিপূর্ণ HTTP স্ট্যাটাস কোড আসলে (যেমন 500, 400)
                    return response.json().then(errData => { throw new Error(errData.error || ` সার্ভার ত্রুটি: ${response.status}`) });
                }
                return response.json();
            })
            .then(data => {
                if(loadingText) loadingText.style.display = 'none';

                if (data.error) {
                    feedbackDiv.textContent = `ত্রুটি: ${data.error}`;
                    feedbackDiv.className = 'feedback feedback-incorrect';
                    // গুরুতর ত্রুটির ক্ষেত্রে বাটনগুলো আবার এনাবল করা যেতে পারে, কিন্তু সাধারণত এটি করা হয় না
                    return;
                }

                const actualCorrectKeyFromServer = data.correct_option_key;
                const userWasCorrect = data.correct;

                // স্টাইল প্রয়োগ করুন
                applyAnswerStyles(selectedOptionKey, actualCorrectKeyFromServer, userWasCorrect);

                if (userWasCorrect) {
                    feedbackDiv.textContent = 'সঠিক উত্তর!';
                    feedbackDiv.className = 'feedback feedback-correct';
                } else {
                    feedbackDiv.textContent = 'ভুল উত্তর। সঠিক উত্তরটি সবুজ করা হয়েছে।';
                    feedbackDiv.className = 'feedback feedback-incorrect';
                }

                if (scoreSpan && data.current_score !== undefined) {
                    scoreSpan.textContent = data.current_score;
                }
            })
            .catch(error => {
                if(loadingText) loadingText.style.display = 'none';
                feedbackDiv.textContent = `একটি সমস্যা হয়েছে: ${error.message}`;
                feedbackDiv.className = 'feedback feedback-incorrect';
                console.error('Fetch Error:', error);
                // ব্যবহারকারীকে আবার চেষ্টা করার সুযোগ দিতে বাটনগুলো এনাবল করা যেতে পারে,
                // তবে সাবধানে করতে হবে যাতে ডুপ্লিকেট সাবমিশন না হয়।
                // optionButtons.forEach(btn => btn.disabled = false); // আপাতত এটি নিষ্ক্রিয় রাখা হলো
            });
        });
    });
});
