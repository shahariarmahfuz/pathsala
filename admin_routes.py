# quiz_app/admin_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
import json
import psycopg2 # psycopg2 এরর এবং অন্যান্য ব্যবহারের জন্য
import psycopg2.extras # DictCursor ব্যবহারের জন্য
from database import get_db
from auth import login_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# --- Helper function ---
def get_subjects_for_admin_forms(conn):
    subjects = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subject_rows = cursor.fetchall()
        subjects = [dict(row) for row in subject_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error fetching subjects for admin forms: {e}")
    finally:
        if cursor: cursor.close()
    return subjects

# --- Admin Dashboard, Subjects, Chapters ---
@admin_bp.route('/')
@login_required
def dashboard():
    return render_template('admin/admin_dashboard.html')

@admin_bp.route('/subjects', methods=['GET', 'POST'])
@login_required
def manage_subjects():
    conn = get_db()
    cursor = None
    try:
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            if name:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO subjects (name) VALUES (%s)", (name,))
                    conn.commit()
                    flash('বিষয় সফলভাবে যোগ করা হয়েছে!', 'success')
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    flash('এই নামের বিষয় ইতিমধ্যে রয়েছে।', 'error')
                except (Exception, psycopg2.Error) as e:
                    conn.rollback()
                    current_app.logger.error(f"Error adding subject: {e}")
                    flash(f'বিষয় যোগ করতে সমস্যা হয়েছে: {e}', 'error')
            else:
                flash('বিষয়ের নাম দিন।', 'error')
            if cursor: cursor.close()
            return redirect(url_for('admin.manage_subjects'))

        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subjects_rows = cursor.fetchall()
        subjects = [dict(row) for row in subjects_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error in manage_subjects: {e}")
        flash("ডেটা আনতে সমস্যা হয়েছে।", "error")
        subjects = []
    finally:
        if cursor: cursor.close()
    return render_template('admin/manage_subjects.html', subjects=subjects)

@admin_bp.route('/chapters', methods=['GET', 'POST'])
@login_required
def manage_chapters():
    conn = get_db()
    cursor = None
    try:
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            subject_id = request.form.get('subject_id')
            if name and subject_id:
                try:
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO chapters (name, subject_id) VALUES (%s, %s)", (name, int(subject_id)))
                    conn.commit()
                    flash('অধ্যায় সফলভাবে যোগ করা হয়েছে!', 'success')
                except psycopg2.errors.UniqueViolation:
                    conn.rollback()
                    flash('এই বিষয়ে এই নামের অধ্যায় ইতিমধ্যে রয়েছে।', 'error')
                except (Exception, psycopg2.Error) as e:
                    conn.rollback()
                    current_app.logger.error(f"Error adding chapter: {e}")
                    flash(f'অধ্যায় যোগ করতে সমস্যা হয়েছে: {e}', 'error')
            else:
                flash('অধ্যায়ের নাম এবং বিষয় নির্বাচন করুন।', 'error')
            if cursor: cursor.close()
            return redirect(url_for('admin.manage_chapters'))

        subjects = get_subjects_for_admin_forms(conn) # Using helper
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("""
            SELECT c.id, c.name as chapter_name, s.name as subject_name, s.id as subject_id
            FROM chapters c JOIN subjects s ON c.subject_id = s.id 
            ORDER BY s.name, c.name
        """)
        chapters_with_subjects_rows = cursor.fetchall()
        chapters_with_subjects = [dict(row) for row in chapters_with_subjects_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error in manage_chapters: {e}")
        flash("ডেটা আনতে সমস্যা হয়েছে।", "error")
        subjects = []
        chapters_with_subjects = []
    finally:
        if cursor: cursor.close()
    return render_template('admin/manage_chapters.html', subjects=subjects, chapters_with_subjects=chapters_with_subjects)

# --- Routes for Adding New Content (MCQ, SQ, CQ) ---
@admin_bp.route('/mcqs/add_form', methods=['GET'])
@login_required
def add_mcq_form():
    conn = get_db()
    subjects = get_subjects_for_admin_forms(conn)
    chapter_id_preselect = request.args.get('chapter_id', type=int)
    mcq_data_for_preselect = None
    if chapter_id_preselect:
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (chapter_id_preselect,))
            chapter_info = cursor.fetchone()
            if chapter_info:
                mcq_data_for_preselect = {'subject_id': chapter_info['subject_id'], 'chapter_id': chapter_id_preselect}
        except (Exception, psycopg2.Error) as e:
            current_app.logger.error(f"Error preselecting chapter in add_mcq_form: {e}")
        finally:
            if cursor: cursor.close()
    return render_template('admin/add_mcq.html', 
                           subjects=subjects, 
                           mcq_data=mcq_data_for_preselect, 
                           form_action=url_for('admin.save_new_mcq'), 
                           is_edit_mode=False)

@admin_bp.route('/mcqs/save_new', methods=['POST'])
@login_required
def save_new_mcq():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_single')
        question_text = request.form.get('question_text_single', '').strip()
        option_a = request.form.get('option_a_single', '').strip()
        option_b = request.form.get('option_b_single', '').strip()
        option_c = request.form.get('option_c_single', '').strip()
        option_d = request.form.get('option_d_single', '').strip()
        correct_option = request.form.get('correct_option_single')

        if not all([chapter_id, question_text, option_a, option_b, option_c, option_d, correct_option]):
            flash('অনুগ্রহ করে একক MCQ এর সব ঘর পূরণ করুন এবং অধ্যায় নির্বাচন করুন।', 'error_mcq_single')
        else:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO questions (chapter_id, question_text, option_a, option_b, option_c, option_d, correct_option)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (int(chapter_id), question_text, option_a, option_b, option_c, option_d, correct_option))
            conn.commit()
            flash('একক MCQ সফলভাবে যোগ করা হয়েছে!', 'success_mcq_single')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error adding single MCQ: {e}")
        flash(f'একক MCQ যোগ করতে সমস্যা হয়েছে: {e}', 'error_mcq_single')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_mcq_form'))

@admin_bp.route('/mcqs/bulk_add', methods=['POST'])
@login_required
def bulk_add_mcq():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_bulk_mcq')
        json_data_string = request.form.get('json_data_mcq', '').strip()

        if not chapter_id:
            flash('MCQ এর জন্য অনুগ্রহ করে বিষয় এবং অধ্যায় নির্বাচন করুন।', 'error_mcq_bulk')
            return redirect(url_for('admin.add_mcq_form'))
        if not json_data_string:
            flash('MCQ এর জন্য অনুগ্রহ করে JSON ডেটা প্রদান করুন।', 'error_mcq_bulk')
            return redirect(url_for('admin.add_mcq_form'))

        mcqs_to_insert = []
        validation_errors = []

        parsed_mcqs = json.loads(json_data_string) # JSONDecodeError এখানে ধরা হবে
        if not isinstance(parsed_mcqs, list):
            validation_errors.append("MCQ JSON ডেটা অবশ্যই একটি তালিকা (list) হতে হবে।")
        else:
            for index, mcq_data in enumerate(parsed_mcqs):
                if not isinstance(mcq_data, dict):
                    validation_errors.append(f"MCQ #{index+1}: প্রতিটি MCQ একটি অবজেক্ট (dictionary) হতে হবে।")
                    continue
                required_keys = ["question_text", "option_a", "option_b", "option_c", "option_d", "correct_option"]
                current_mcq_errors = []
                temp_mcq_obj = {}
                for key in required_keys:
                    value = str(mcq_data.get(key, "")).strip()
                    if not value:
                        current_mcq_errors.append(f"MCQ #{index+1}, '{key}' অনুপস্থিত বা খালি।")
                    temp_mcq_obj[key] = value

                correct_opt_val = temp_mcq_obj.get("correct_option", "").lower()
                if correct_opt_val not in ['a', 'b', 'c', 'd']:
                    current_mcq_errors.append(f"MCQ #{index+1}, অবৈধ 'correct_option': '{correct_opt_val}'। 'a', 'b', 'c', বা 'd' হতে হবে।")

                if current_mcq_errors:
                    validation_errors.extend(current_mcq_errors)
                else:
                    mcqs_to_insert.append((
                        int(chapter_id), temp_mcq_obj["question_text"],
                        temp_mcq_obj["option_a"], temp_mcq_obj["option_b"],
                        temp_mcq_obj["option_c"], temp_mcq_obj["option_d"],
                        correct_opt_val
                    ))

        if validation_errors:
            for error_msg in validation_errors:
                flash(error_msg, 'error_mcq_bulk')
        elif mcqs_to_insert:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO questions (chapter_id, question_text, option_a, option_b, option_c, option_d, correct_option)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, mcqs_to_insert)
            conn.commit()
            flash(f"{len(mcqs_to_insert)} টি MCQ সফলভাবে যোগ করা হয়েছে!", 'success_mcq_bulk')
        else:
            if not validation_errors: # যদি কোনো ভ্যালিডেশন এরর না থাকে কিন্তু যোগ করার কিছু না পাওয়া যায়
                flash("MCQ যোগ করার জন্য কোনো সঠিক ডেটা পাওয়া যায়নি (JSON খালি অথবা সব ডেটা ত্রুটিপূর্ণ)।", 'info_mcq_bulk')

    except json.JSONDecodeError:
        flash("MCQ এর জন্য অবৈধ JSON ফরম্যাট। অনুগ্রহ করে আপনার JSON ডেটা পরীক্ষা করুন।", "error_mcq_bulk")
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error bulk adding MCQs: {e}")
        flash(f"MCQ যোগ করার সময় ডাটাবেসে সমস্যা হয়েছে: {e}", 'error_mcq_bulk')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_mcq_form'))

@admin_bp.route('/short_questions/add_form', methods=['GET'])
@login_required
def add_short_question_form():
    conn = get_db()
    subjects = get_subjects_for_admin_forms(conn)
    chapter_id_preselect = request.args.get('chapter_id', type=int)
    sq_data = None
    if chapter_id_preselect:
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (chapter_id_preselect,))
            chapter_info = cursor.fetchone()
            if chapter_info:
                sq_data = {'subject_id': chapter_info['subject_id'], 'chapter_id': chapter_id_preselect}
        except (Exception, psycopg2.Error) as e:
            current_app.logger.error(f"Error preselecting chapter in add_sq_form: {e}")
        finally:
            if cursor: cursor.close()
    return render_template('admin/add_short_question.html', 
                           subjects=subjects, 
                           sq_data=sq_data, 
                           form_action=url_for('admin.save_new_short_question'), 
                           is_edit_mode=False)

@admin_bp.route('/short_questions/save_new', methods=['POST'])
@login_required
def save_new_short_question():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_single_sq')
        question_text = request.form.get('question_text_single_sq', '').strip()
        answer_text = request.form.get('answer_text_single_sq', '').strip()
        if not all([chapter_id, question_text, answer_text]):
            flash('অনুগ্রহ করে সংক্ষিপ্ত প্রশ্নের সব ঘর পূরণ করুন এবং অধ্যায় নির্বাচন করুন।', 'error_sq_single')
        else:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO short_questions (chapter_id, question_text, answer_text) VALUES (%s, %s, %s)", 
                         (int(chapter_id), question_text, answer_text))
            conn.commit()
            flash('একক সংক্ষিপ্ত প্রশ্ন সফলভাবে যোগ করা হয়েছে!', 'success_sq_single')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error adding single SQ: {e}")
        flash(f'একক সংক্ষিপ্ত প্রশ্ন যোগ করতে সমস্যা হয়েছে: {e}', 'error_sq_single')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_short_question_form'))

@admin_bp.route('/short_questions/bulk_add', methods=['POST'])
@login_required
def bulk_add_short_question():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_bulk_sq')
        json_data_string = request.form.get('json_data_sq', '').strip()
        if not chapter_id:
            flash('সংক্ষিপ্ত প্রশ্নের জন্য অনুগ্রহ করে বিষয় এবং অধ্যায় নির্বাচন করুন।', 'error_sq_bulk')
            return redirect(url_for('admin.add_short_question_form'))
        if not json_data_string:
            flash('সংক্ষিপ্ত প্রশ্নের জন্য অনুগ্রহ করে JSON ডেটা প্রদান করুন।', 'error_sq_bulk')
            return redirect(url_for('admin.add_short_question_form'))
        sq_to_insert = []
        validation_errors = []
        parsed_sqs = json.loads(json_data_string)
        if not isinstance(parsed_sqs, list):
            validation_errors.append("সংক্ষিপ্ত প্রশ্নের JSON ডেটা অবশ্যই একটি তালিকা (list) হতে হবে।")
        else:
            for index, sq_data in enumerate(parsed_sqs):
                if not isinstance(sq_data, dict):
                    validation_errors.append(f"সংক্ষিপ্ত প্রশ্ন #{index+1}: প্রতিটি প্রশ্ন একটি অবজেক্ট (dictionary) হতে হবে।")
                    continue
                required_keys = ["question_text", "answer_text"]
                current_sq_errors = []
                temp_sq_obj = {}
                for key in required_keys:
                    value = str(sq_data.get(key, "")).strip()
                    if not value:
                        current_sq_errors.append(f"সংক্ষিপ্ত প্রশ্ন #{index+1}, '{key}' অনুপস্থিত বা খালি।")
                    temp_sq_obj[key] = value
                if current_sq_errors:
                    validation_errors.extend(current_sq_errors)
                else:
                    sq_to_insert.append((int(chapter_id), temp_sq_obj["question_text"], temp_sq_obj["answer_text"]))
        if validation_errors:
            for error_msg in validation_errors:
                flash(error_msg, 'error_sq_bulk')
        elif sq_to_insert:
            cursor = conn.cursor()
            cursor.executemany("INSERT INTO short_questions (chapter_id, question_text, answer_text) VALUES (%s, %s, %s)", sq_to_insert)
            conn.commit()
            flash(f"{len(sq_to_insert)} টি সংক্ষিপ্ত প্রশ্ন সফলভাবে যোগ করা হয়েছে!", 'success_sq_bulk')
        else:
            if not validation_errors:
                flash("সংক্ষিপ্ত প্রশ্ন যোগ করার জন্য কোনো সঠিক ডেটা পাওয়া যায়নি।", 'info_sq_bulk')
    except json.JSONDecodeError:
        flash("সংক্ষিপ্ত প্রশ্নের জন্য অবৈধ JSON ফরম্যাট।", "error_sq_bulk")
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error bulk adding short questions: {e}")
        flash(f"সংক্ষিপ্ত প্রশ্ন যোগ করার সময় ডাটাবেসে সমস্যা হয়েছে: {e}", 'error_sq_bulk')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_short_question_form'))

@admin_bp.route('/creative_questions/add_form', methods=['GET'])
@login_required
def add_creative_question_form():
    conn = get_db()
    subjects = get_subjects_for_admin_forms(conn)
    chapter_id_preselect = request.args.get('chapter_id', type=int)
    cq_data = None
    if chapter_id_preselect:
        cursor = None
        try:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (chapter_id_preselect,))
            chapter_info = cursor.fetchone()
            if chapter_info:
                cq_data = {'subject_id': chapter_info['subject_id'], 'chapter_id': chapter_id_preselect}
        except (Exception, psycopg2.Error) as e:
             current_app.logger.error(f"Error preselecting chapter in add_cq_form: {e}")
        finally:
            if cursor: cursor.close()
    return render_template('admin/add_creative_question.html', 
                           subjects=subjects, cq_data=cq_data, 
                           form_action=url_for('admin.save_new_creative_question'), 
                           is_edit_mode=False)

@admin_bp.route('/creative_questions/save_new', methods=['POST'])
@login_required
def save_new_creative_question():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_single_cq')
        uddipak_text = request.form.get('uddipak_text_single_cq', '').strip()
        question_ka = request.form.get('question_ka_single_cq', '').strip()
        answer_ka = request.form.get('answer_ka_single_cq', '').strip()
        question_kha = request.form.get('question_kha_single_cq', '').strip()
        answer_kha = request.form.get('answer_kha_single_cq', '').strip()
        question_ga = request.form.get('question_ga_single_cq', '').strip()
        answer_ga = request.form.get('answer_ga_single_cq', '').strip()
        question_gha = request.form.get('question_gha_single_cq', '').strip()
        answer_gha = request.form.get('answer_gha_single_cq', '').strip()
        required_fields = [chapter_id, uddipak_text, question_ka, answer_ka, question_kha, answer_kha, question_ga, answer_ga, question_gha, answer_gha]
        if not all(field and field.strip() for field in required_fields):
            flash('অনুগ্রহ করে সৃজনশীল প্রশ্নের সব ঘর পূরণ করুন এবং অধ্যায় নির্বাচন করুন।', 'error_cq_single')
        else:
            cursor = conn.cursor()
            cursor.execute("""INSERT INTO creative_questions (chapter_id, uddipak_text, question_ka, answer_ka, question_kha, answer_kha, question_ga, answer_ga, question_gha, answer_gha)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                             (int(chapter_id), uddipak_text, question_ka, answer_ka, question_kha, answer_kha, question_ga, answer_ga, question_gha, answer_gha))
            conn.commit()
            flash('একক সৃজনশীল প্রশ্ন সফলভাবে যোগ করা হয়েছে!', 'success_cq_single')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error adding single CQ: {e}")
        flash(f'একক সৃজনশীল প্রশ্ন যোগ করতে সমস্যা হয়েছে: {e}', 'error_cq_single')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_creative_question_form'))

@admin_bp.route('/creative_questions/bulk_add', methods=['POST'])
@login_required
def bulk_add_creative_question():
    conn = get_db()
    cursor = None
    try:
        chapter_id = request.form.get('chapter_id_bulk_cq')
        json_data_string = request.form.get('json_data_cq', '').strip()
        if not chapter_id:
            flash('সৃজনশীল প্রশ্নের জন্য অনুগ্রহ করে বিষয় এবং অধ্যায় নির্বাচন করুন।', 'error_cq_bulk')
            return redirect(url_for('admin.add_creative_question_form'))
        if not json_data_string:
            flash('সৃজনশীল প্রশ্নের জন্য অনুগ্রহ করে JSON ডেটা প্রদান করুন।', 'error_cq_bulk')
            return redirect(url_for('admin.add_creative_question_form'))
        cq_to_insert = []
        validation_errors = []
        parsed_cqs = json.loads(json_data_string)
        if not isinstance(parsed_cqs, list):
            validation_errors.append("সৃজনশীল প্রশ্নের JSON ডেটা অবশ্যই একটি তালিকা (list) হতে হবে।")
        else:
            for index, cq_data in enumerate(parsed_cqs):
                if not isinstance(cq_data, dict):
                    validation_errors.append(f"সৃজনশীল প্রশ্ন #{index+1}: প্রতিটি প্রশ্ন একটি অবজেক্ট (dictionary) হতে হবে।")
                    continue
                required_keys = ["uddipak_text", "question_ka", "answer_ka", "question_kha", "answer_kha", "question_ga", "answer_ga", "question_gha", "answer_gha"]
                current_cq_errors = []
                temp_cq_obj = {}
                for key in required_keys:
                    value = str(cq_data.get(key, "")).strip()
                    if not value:
                        current_cq_errors.append(f"সৃজনশীল প্রশ্ন #{index+1}, '{key}' অনুপস্থিত বা খালি।")
                    temp_cq_obj[key] = value
                if current_cq_errors:
                    validation_errors.extend(current_cq_errors)
                else:
                    cq_to_insert.append((
                        int(chapter_id), temp_cq_obj["uddipak_text"],
                        temp_cq_obj["question_ka"], temp_cq_obj["answer_ka"],
                        temp_cq_obj["question_kha"], temp_cq_obj["answer_kha"],
                        temp_cq_obj["question_ga"], temp_cq_obj["answer_ga"],
                        temp_cq_obj["question_gha"], temp_cq_obj["answer_gha"]
                    ))
        if validation_errors:
            for error_msg in validation_errors:
                flash(error_msg, 'error_cq_bulk')
        elif cq_to_insert:
            cursor = conn.cursor()
            cursor.executemany("""INSERT INTO creative_questions (chapter_id, uddipak_text, question_ka, answer_ka, question_kha, answer_kha, question_ga, answer_ga, question_gha, answer_gha)
                                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", cq_to_insert)
            conn.commit()
            flash(f"{len(cq_to_insert)} টি সৃজনশীল প্রশ্ন সফলভাবে যোগ করা হয়েছে!", 'success_cq_bulk')
        else:
            if not validation_errors:
                flash("সৃজনশীল প্রশ্ন যোগ করার জন্য কোনো সঠিক ডেটা পাওয়া যায়নি।", 'info_cq_bulk')
    except json.JSONDecodeError:
        flash("সৃজনশীল প্রশ্নের জন্য অবৈধ JSON ফরম্যাট।", "error_cq_bulk")
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error bulk adding creative questions: {e}")
        flash(f"সৃজনশীল প্রশ্ন যোগ করার সময় ডাটাবেসে সমস্যা হয়েছে: {e}", 'error_cq_bulk')
    finally:
        if cursor: cursor.close()
    return redirect(url_for('admin.add_creative_question_form'))