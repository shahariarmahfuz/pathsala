# quiz_app/public_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, flash, g, current_app
import random 
import psycopg2 # psycopg2 এরর এবং অন্যান্য ব্যবহারের জন্য
import psycopg2.extras # DictCursor ব্যবহারের জন্য
from database import get_db # database.py থেকে get_db
from auth import login_required # auth.py থেকে login_required ইম্পোর্ট

public_bp = Blueprint('public', __name__)

# --- Main Homepage Route ---
@public_bp.route('/')
def main_homepage():
    return render_template('index.html')

# --- API for dynamic content (সাধারণভাবে ব্যবহৃত) ---
@public_bp.route('/api/get_chapters/<int:subject_id>')
def api_get_chapters_for_subject(subject_id):
    conn = get_db()
    chapters = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT id, name FROM chapters WHERE subject_id = %s ORDER BY name", (subject_id,))
        chapters_rows = cursor.fetchall()
        chapters = [dict(row) for row in chapters_rows]
    except (Exception, psycopg2.Error) as error:
        current_app.logger.error(f"API Error fetching chapters for subject {subject_id}: {error}")
    finally:
        if cursor:
            cursor.close()
    return jsonify({'chapters': chapters})

# --- User Routes for MCQ Quiz ---
@public_bp.route('/mcq')
def mcq_home_page():
    conn = get_db()
    subjects = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subject_rows = cursor.fetchall()
        subjects = [dict(row) for row in subject_rows]
    except (Exception, psycopg2.Error) as error:
        current_app.logger.error(f"Error fetching subjects for MCQ home: {error}")
        flash("বিষয় আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor:
            cursor.close()
    return render_template('mcq_home.html', subjects=subjects)

@public_bp.route('/start_quiz', methods=['POST'])
def start_quiz():
    num_questions_str = request.form.get('num_questions')
    subject_id = request.form.get('subject_id') 
    chapter_id = request.form.get('chapter_id')
    quiz_mode = request.form.get('quiz_mode', 'normal')

    if not all([num_questions_str, subject_id, chapter_id, quiz_mode]):
        flash("অনুগ্রহ করে বিষয়, অধ্যায়, প্রশ্নের সংখ্যা এবং কুইজের ধরণ নির্বাচন করুন।", "error")
        return redirect(url_for('public.mcq_home_page'))

    if not num_questions_str.isdigit() or int(num_questions_str) <= 0:
        flash("অনুগ্রহ করে প্রশ্নের একটি সঠিক সংখ্যা দিন।", "error")
        return redirect(url_for('public.mcq_home_page'))

    num_questions_to_select = int(num_questions_str)
    conn = get_db()
    cursor = None
    all_questions_for_chapter = []

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM questions WHERE chapter_id = %s", (chapter_id,))
        all_questions_for_chapter_rows = cursor.fetchall()
        all_questions_for_chapter = [dict(row) for row in all_questions_for_chapter_rows]
    except (Exception, psycopg2.Error) as error:
        current_app.logger.error(f"Error fetching MCQs for chapter {chapter_id}: {error}")
        flash("প্রশ্ন আনতে সমস্যা হয়েছে।", "error")
        return redirect(url_for('public.mcq_home_page'))
    finally:
        if cursor:
            cursor.close()

    if not all_questions_for_chapter:
        flash("এই অধ্যায়ে কোনো MCQ প্রশ্ন পাওয়া যায়নি।", "warning")
        return redirect(url_for('public.mcq_home_page'))

    processed_questions_with_attempt_status = []
    attempted_mcq_ids = set()
    if g.user:
        user_id = g.user['id']
        cursor_attempted = None
        try:
            cursor_attempted = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor_attempted.execute('SELECT mcq_id FROM user_attempted_mcqs WHERE user_id = %s', (user_id,))
            attempted_mcqs_tuples = cursor_attempted.fetchall()
            attempted_mcq_ids = {item['mcq_id'] for item in attempted_mcqs_tuples}
        except (Exception, psycopg2.Error) as error:
            current_app.logger.error(f"Error fetching attempted MCQs for user {user_id}: {error}")
        finally:
            if cursor_attempted:
                cursor_attempted.close()

    for q_dict in all_questions_for_chapter:
        q_dict['is_attempted_by_user'] = q_dict['id'] in attempted_mcq_ids if g.user else False
        processed_questions_with_attempt_status.append(q_dict)

    random.shuffle(processed_questions_with_attempt_status)

    actual_num_questions_available = len(processed_questions_with_attempt_status)
    if num_questions_to_select > actual_num_questions_available:
        num_questions_to_select = actual_num_questions_available
        flash(f"আপনার অনুরোধকৃত সংখ্যক MCQ প্রশ্ন এই অধ্যায়ে নেই। {actual_num_questions_available}টি প্রশ্ন দেখানো হচ্ছে।", "info")

    if num_questions_to_select == 0:
        flash("MCQ কুইজের জন্য কোনো প্রশ্ন নির্বাচন করা হয়নি বা উপলব্ধ নেই।", "error")
        return redirect(url_for('public.mcq_home_page'))

    selected_questions = processed_questions_with_attempt_status[:num_questions_to_select]

    session['quiz_questions'] = selected_questions
    session['current_question_index'] = 0
    session['score'] = 0
    session['answers_submitted'] = {}
    session['quiz_mode'] = quiz_mode 
    if quiz_mode == 'timed':
        session['time_per_question'] = 30 
    else:
        session.pop('time_per_question', None)

    if not session['quiz_questions']:
        flash("MCQ কুইজ শুরু করতে সমস্যা হয়েছে।", "error")
        return redirect(url_for('public.mcq_home_page'))
    return redirect(url_for('public.quiz_page'))

@public_bp.route('/quiz')
def quiz_page():
    if 'quiz_questions' not in session or not session.get('quiz_questions'):
        flash("MCQ কুইজ সেশন শুরু হয়নি বা কোনো প্রশ্ন নেই।", "warning")
        return redirect(url_for('public.mcq_home_page'))

    current_index = session.get('current_question_index', 0)
    quiz_questions = session.get('quiz_questions', [])

    if current_index >= len(quiz_questions):
        flash("MCQ কুইজ ইতিমধ্যে সম্পন্ন হয়েছে।", "info") 
        return redirect(url_for('public.mcq_home_page')) 

    question_data = quiz_questions[current_index] 
    question_id_str = str(question_data['id'])
    Youtubeed = question_id_str in session.get('answers_submitted', {})
    previous_submission_details = None
    if Youtubeed:
        previous_submission_details = session['answers_submitted'][question_id_str]

    quiz_mode = session.get('quiz_mode', 'normal')
    time_per_question = session.get('time_per_question', 0)

    return render_template('quiz.html', 
                           question=question_data, 
                           question_number=current_index + 1,
                           total_questions=len(quiz_questions), 
                           current_score=session.get('score',0),
                           Youtubeed=Youtubeed, 
                           previous_submission=previous_submission_details,
                           quiz_mode=quiz_mode, 
                           time_limit=time_per_question)

@public_bp.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'quiz_questions' not in session: 
        return jsonify({'error': 'কুইজ সেশন শুরু হয়নি'}), 400

    data = request.get_json()
    question_id = data.get('question_id')
    user_answer_key = data.get('answer') 

    if question_id is None or user_answer_key is None: 
        return jsonify({'error': 'অসম্পূর্ণ ডেটা'}), 400

    str_question_id = str(question_id)
    quiz_questions = session.get('quiz_questions', [])
    current_q_data = next((q for q in quiz_questions if q['id'] == question_id), None)

    if not current_q_data: 
        return jsonify({'error': 'প্রশ্ন পাওয়া যায়নি'}), 400

    answers_submitted_map = session.get('answers_submitted', {})
    if str_question_id in answers_submitted_map:
        prev_sub = answers_submitted_map[str_question_id]
        return jsonify({
            'already_answered': True, 'correct': prev_sub['correct'], 
            'correct_option_key': prev_sub['correct_option_key'],
            'user_choice_key': prev_sub['user_choice_key'], 
            'current_score': session.get('score', 0),
            'total_questions_in_quiz': len(quiz_questions)
        })

    is_correct = False
    if user_answer_key == 'TIMEOUT':
        is_correct = False 
    else:
        is_correct = (user_answer_key == current_q_data['correct_option'])

    current_score = session.get('score', 0)
    if is_correct:
        current_score += 1
        session['score'] = current_score

    answers_submitted_map[str_question_id] = {
        'correct': is_correct, 
        'correct_option_key': current_q_data['correct_option'], 
        'user_choice_key': user_answer_key if user_answer_key != 'TIMEOUT' else None 
    }
    session['answers_submitted'] = answers_submitted_map
    session.modified = True

    if g.user:
        user_id = g.user['id']
        db = get_db()
        cursor = None
        try:
            cursor = db.cursor()
            # PostgreSQL এর জন্য ON CONFLICT
            cursor.execute(
                """
                INSERT INTO user_attempted_mcqs (user_id, mcq_id) 
                VALUES (%s, %s) 
                ON CONFLICT (user_id, mcq_id) DO NOTHING
                """, (user_id, question_id)
            )
            db.commit()
        except (Exception, psycopg2.Error) as e:
            db.rollback()
            current_app.logger.error(f"Error marking MCQ {question_id} as attempted for user {user_id}: {e}")
        finally:
            if cursor: cursor.close()

    return jsonify({
        'correct': is_correct, 
        'correct_option_key': current_q_data['correct_option'], 
        'user_choice_key': user_answer_key, 
        'current_score': current_score, 
        'total_questions_in_quiz': len(quiz_questions), 
        'already_answered': False
    })

@public_bp.route('/next_question', methods=['POST'])
def next_question():
    if 'quiz_questions' not in session:
        flash("সেশন খুঁজে পাওয়া যায়নি।", "error")
        return redirect(url_for('public.mcq_home_page'))
    current_index = session.get('current_question_index', 0) + 1
    session['current_question_index'] = current_index
    quiz_questions_list = session.get('quiz_questions', [])
    if current_index >= len(quiz_questions_list):
        final_score, total_q = session.get('score', 0), len(quiz_questions_list) if quiz_questions_list else 0
        flash(f'MCQ কুইজ সম্পন্ন হয়েছে! আপনার চূড়ান্ত স্কোর: {final_score} / {total_q}', 'success')
        keys_to_pop = ['quiz_questions', 'current_question_index', 'score', 'answers_submitted', 'quiz_mode', 'time_per_question']
        for key in keys_to_pop: 
            session.pop(key, None)
        return redirect(url_for('public.mcq_home_page'))
    return redirect(url_for('public.quiz_page'))

# --- User Routes for Short Questions ---
@public_bp.route('/short-questions')
@login_required
def short_questions_home():
    conn = get_db()
    subjects = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subject_rows = cursor.fetchall()
        subjects = [dict(row) for row in subject_rows]
    except (Exception, psycopg2.Error) as error:
        current_app.logger.error(f"Error fetching subjects for SQ home: {error}")
        flash("বিষয় আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor: cursor.close()
    return render_template('short_questions_home.html', subjects=subjects)

@public_bp.route('/api/short_questions/<int:chapter_id>')
@login_required
def api_fetch_short_questions(chapter_id):
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page
    db = get_db()
    user_id = g.user['id']
    cursor = None
    questions_for_page = []
    total_items = 0
    total_pages = 0

    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)

        cursor.execute('SELECT short_question_id FROM user_seen_short_questions WHERE user_id = %s', (user_id,))
        seen_sq_ids_tuples = cursor.fetchall()
        seen_sq_ids = {item['short_question_id'] for item in seen_sq_ids_tuples}

        cursor.execute('SELECT COUNT(id) as count FROM short_questions WHERE chapter_id = %s', (chapter_id,))
        total_questions_count_row = cursor.fetchone()
        total_items = total_questions_count_row['count'] if total_questions_count_row else 0
        total_pages = (total_items + per_page - 1) // per_page if total_items > 0 else 0

        if page < 1 and total_pages > 0 : page = 1
        if page > total_pages and total_pages > 0 : page = total_pages

        cursor.execute(
            "SELECT id, question_text, answer_text FROM short_questions WHERE chapter_id = %s ORDER BY id LIMIT %s OFFSET %s",
            (chapter_id, per_page, offset)
        )
        current_page_questions = cursor.fetchall()

        ids_to_mark_seen_this_batch = []
        for row in current_page_questions:
            question_dict = dict(row)
            question_dict['is_seen_by_user'] = row['id'] in seen_sq_ids
            questions_for_page.append(question_dict)
            if not question_dict['is_seen_by_user']:
                 ids_to_mark_seen_this_batch.append((user_id, row['id']))

        if ids_to_mark_seen_this_batch:
            # psycopg2 executemany এর জন্য ডেটা একটি তালিকা হতে হবে
            cursor.executemany(
                'INSERT INTO user_seen_short_questions (user_id, short_question_id) VALUES (%s, %s) ON CONFLICT (user_id, short_question_id) DO NOTHING',
                ids_to_mark_seen_this_batch
            )
            db.commit()

    except (Exception, psycopg2.Error) as e:
        db.rollback()
        current_app.logger.error(f"API Error fetching short questions for chapter {chapter_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()

    return jsonify({'short_questions': questions_for_page, 'current_page': page, 'total_pages': total_pages, 'has_next': page < total_pages, 'has_prev': page > 1, 'total_items': total_items})

# --- User Route for Creative Questions ---
@public_bp.route('/creative-questions')
@login_required
def creative_questions_home():
    conn = get_db()
    subjects = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subject_rows = cursor.fetchall()
        subjects = [dict(row) for row in subject_rows]
    except (Exception, psycopg2.Error) as error:
        current_app.logger.error(f"Error fetching subjects for CQ home: {error}")
        flash("বিষয় আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor: cursor.close()
    return render_template('creative_questions_home.html', subjects=subjects)

@public_bp.route('/api/creative_question/<int:chapter_id>')
@login_required
def api_fetch_creative_question(chapter_id):
    page = request.args.get('page', 1, type=int)
    per_page = 1 
    offset = (page - 1) * per_page
    db = get_db()
    user_id = g.user['id']
    cursor = None
    question_data = None
    total_items = 0
    total_pages = 0
    is_seen = False

    try:
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT COUNT(id) as count FROM creative_questions WHERE chapter_id = %s', (chapter_id,))
        total_questions_count_row = cursor.fetchone()
        total_items = total_questions_count_row['count'] if total_questions_count_row else 0
        total_pages = total_items 

        if page < 1 and total_pages > 0 : page = 1
        # যদি পৃষ্ঠা সীমার বাইরে হয়, তাহলে creative_q_row None হবে

        cursor.execute(
            """SELECT id, uddipak_text, question_ka, answer_ka, question_kha, answer_kha,
                      question_ga, answer_ga, question_gha, answer_gha
               FROM creative_questions WHERE chapter_id = %s ORDER BY id LIMIT %s OFFSET %s""", 
            (chapter_id, per_page, offset)
        )
        creative_q_row = cursor.fetchone()

        if creative_q_row:
            question_data = dict(creative_q_row)
            cursor.execute('SELECT 1 FROM user_seen_creative_questions WHERE user_id = %s AND creative_question_id = %s', 
                           (user_id, question_data['id']))
            seen_check = cursor.fetchone()
            is_seen = bool(seen_check)
            question_data['is_seen_by_user'] = is_seen

            if not is_seen:
                cursor.execute(
                    """
                    INSERT INTO user_seen_creative_questions (user_id, creative_question_id) 
                    VALUES (%s, %s) 
                    ON CONFLICT (user_id, creative_question_id) DO NOTHING
                    """, (user_id, question_data['id'])
                )
                db.commit()

    except (Exception, psycopg2.Error) as e:
        db.rollback()
        current_app.logger.error(f"API Error fetching creative question for chapter {chapter_id}, page {page}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor: cursor.close()

    return jsonify({
        'creative_question': question_data, 
        'current_page': page, 
        'total_pages': total_pages,
        'has_next': page < total_pages if total_pages > 0 else False, 
        'has_prev': page > 1 and total_pages > 0, 
        'total_items': total_items
    })