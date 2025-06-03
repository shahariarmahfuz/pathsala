# quiz_app/manage_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
import psycopg2 # psycopg2 এরর এবং অন্যান্য ব্যবহারের জন্য
import psycopg2.extras # DictCursor ব্যবহারের জন্য
from database import get_db
from auth import login_required

manage_bp = Blueprint('manage', __name__, url_prefix='/admin/manage')

# --- Helper function ---
def get_subjects_for_manage_forms(conn):
    subjects = []
    cursor = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT * FROM subjects ORDER BY name")
        subject_rows = cursor.fetchall()
        subjects = [dict(row) for row in subject_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error fetching subjects for manage forms: {e}")
    finally:
        if cursor: cursor.close()
    return subjects

# --- MCQ Management (List, Edit, Delete) ---
@manage_bp.route('/mcqs', methods=['GET'])
@login_required
def mcqs_list():
    conn = get_db()
    cursor = None
    subjects = get_subjects_for_manage_forms(conn)
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_chapter_id = request.args.get('chapter_id', type=int)
    chapters_for_selected_subject = []
    mcqs = []

    try:
        if selected_subject_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT id, name FROM chapters WHERE subject_id = %s ORDER BY name", (selected_subject_id,))
            chapters_rows = cursor.fetchall()
            chapters_for_selected_subject = [dict(row) for row in chapters_rows]
            cursor.close() # এই কার্সারটি বন্ধ করুন

        if selected_chapter_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM questions WHERE chapter_id = %s ORDER BY id DESC", (selected_chapter_id,))
            mcq_rows = cursor.fetchall()
            mcqs = [dict(row) for row in mcq_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error listing MCQs: {e}")
        flash("MCQ তালিকা আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor: cursor.close()

    return render_template('admin/manage_mcqs.html', 
                           subjects=subjects, 
                           selected_subject_id=selected_subject_id,
                           chapters_for_selected_subject=chapters_for_selected_subject,
                           selected_chapter_id=selected_chapter_id,
                           mcqs=mcqs)

@manage_bp.route('/mcqs/edit/<int:mcq_id>', methods=['GET', 'POST'])
@login_required
def edit_mcq(mcq_id):
    conn = get_db()
    cursor = None
    mcq_item = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            'SELECT q.*, c.subject_id FROM questions q JOIN chapters c ON q.chapter_id = c.id WHERE q.id = %s', 
            (mcq_id,)
        )
        mcq_item_row = cursor.fetchone()
        if mcq_item_row:
            mcq_item = dict(mcq_item_row)
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error fetching MCQ {mcq_id} for edit: {e}")
        flash("MCQ আনতে সমস্যা হয়েছে।", "error")
        return redirect(url_for('manage.mcqs_list'))
    finally:
        if cursor: cursor.close()

    if not mcq_item:
        flash('MCQ খুঁজে পাওয়া যায়নি।', 'error')
        return redirect(url_for('manage.mcqs_list'))

    if request.method == 'POST':
        cursor = None
        try:
            question_text = request.form.get('question_text_single', '').strip()
            option_a = request.form.get('option_a_single', '').strip()
            option_b = request.form.get('option_b_single', '').strip()
            option_c = request.form.get('option_c_single', '').strip()
            option_d = request.form.get('option_d_single', '').strip()
            correct_option = request.form.get('correct_option_single')
            new_chapter_id_str = request.form.get('chapter_id_single')

            if not new_chapter_id_str or not new_chapter_id_str.isdigit():
                flash('অবৈধ অধ্যায় নির্বাচন।', 'error_mcq_single')
            elif not all([question_text, option_a, option_b, option_c, option_d, correct_option]):
                flash('অনুগ্রহ করে সব ঘর পূরণ করুন।', 'error_mcq_single')
            else:
                new_chapter_id = int(new_chapter_id_str)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE questions SET question_text = %s, option_a = %s, option_b = %s, option_c = %s, option_d = %s, 
                                         correct_option = %s, chapter_id = %s
                    WHERE id = %s
                """, (question_text, option_a, option_b, option_c, option_d, correct_option, new_chapter_id, mcq_id))
                conn.commit()
                flash('MCQ সফলভাবে আপডেট করা হয়েছে!', 'success_mcq_single')

                # Get subject_id for redirect
                cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (new_chapter_id,))
                updated_chapter_info = cursor.fetchone()
                updated_subject_id = updated_chapter_info[0] if updated_chapter_info else mcq_item['subject_id']
                return redirect(url_for('manage.mcqs_list', subject_id=updated_subject_id, chapter_id=new_chapter_id))
        except (Exception, psycopg2.Error) as e:
            conn.rollback()
            current_app.logger.error(f"Error updating MCQ {mcq_id}: {e}")
            flash(f'MCQ আপডেট করতে সমস্যা হয়েছে: {e}', 'error_mcq_single')
        finally:
            if cursor: cursor.close()
        # যদি POST এ সমস্যা হয়, ফর্ম আবার দেখানো হবে (নিচের GET অংশের কোড দিয়ে)

    subjects = get_subjects_for_manage_forms(conn)
    return render_template('admin/add_mcq.html', 
                           subjects=subjects, 
                           mcq_data=mcq_item, 
                           form_action=url_for('manage.edit_mcq', mcq_id=mcq_id), 
                           is_edit_mode=True)

@manage_bp.route('/mcqs/delete/<int:mcq_id>', methods=['POST'])
@login_required
def delete_mcq(mcq_id):
    conn = get_db()
    cursor = None
    original_chapter_id = None
    original_subject_id = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT q.chapter_id, c.subject_id FROM questions q JOIN chapters c ON q.chapter_id = c.id WHERE q.id = %s", (mcq_id,))
        mcq_info = cursor.fetchone()
        if mcq_info:
            original_chapter_id = mcq_info['chapter_id']
            original_subject_id = mcq_info['subject_id']

        cursor.execute('DELETE FROM questions WHERE id = %s', (mcq_id,))
        conn.commit()
        flash('MCQ সফলভাবে মুছে ফেলা হয়েছে!', 'success')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting MCQ {mcq_id}: {e}")
        flash(f'MCQ মুছতে সমস্যা হয়েছে: {e}', 'error')
    finally:
        if cursor: cursor.close()

    if original_subject_id and original_chapter_id:
        return redirect(url_for('manage.mcqs_list', subject_id=original_subject_id, chapter_id=original_chapter_id))
    return redirect(url_for('manage.mcqs_list'))

# --- Short Question Management (List, Edit, Delete) ---
@manage_bp.route('/short_questions', methods=['GET'])
@login_required
def short_questions_list():
    conn = get_db()
    cursor = None
    subjects = get_subjects_for_manage_forms(conn)
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_chapter_id = request.args.get('chapter_id', type=int)
    chapters_for_selected_subject = []
    short_questions_data = []

    try:
        if selected_subject_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT id, name FROM chapters WHERE subject_id = %s ORDER BY name", (selected_subject_id,))
            chapters_rows = cursor.fetchall()
            chapters_for_selected_subject = [dict(row) for row in chapters_rows]
            cursor.close()

        if selected_chapter_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM short_questions WHERE chapter_id = %s ORDER BY id DESC", (selected_chapter_id,))
            sq_rows = cursor.fetchall()
            short_questions_data = [dict(row) for row in sq_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error listing Short Questions: {e}")
        flash("সংক্ষিপ্ত প্রশ্ন তালিকা আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor: cursor.close()

    return render_template('admin/manage_short_questions.html', 
                           subjects=subjects, 
                           selected_subject_id=selected_subject_id,
                           chapters_for_selected_subject=chapters_for_selected_subject,
                           selected_chapter_id=selected_chapter_id,
                           short_questions=short_questions_data)

@manage_bp.route('/short_questions/edit/<int:sq_id>', methods=['GET', 'POST'])
@login_required
def edit_short_question(sq_id):
    conn = get_db()
    cursor = None
    sq_item = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT sq.*, c.subject_id FROM short_questions sq JOIN chapters c ON sq.chapter_id = c.id WHERE sq.id = %s', (sq_id,))
        sq_item_row = cursor.fetchone()
        if sq_item_row:
            sq_item = dict(sq_item_row)
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error fetching SQ {sq_id} for edit: {e}")
        flash("সংক্ষিপ্ত প্রশ্ন আনতে সমস্যা হয়েছে।", "error")
        return redirect(url_for('manage.short_questions_list'))
    finally:
        if cursor: cursor.close()

    if not sq_item:
        flash('সংক্ষিপ্ত প্রশ্ন খুঁজে পাওয়া যায়নি।', 'error')
        return redirect(url_for('manage.short_questions_list'))

    if request.method == 'POST':
        cursor = None
        try:
            question_text = request.form.get('question_text_single_sq', '').strip()
            answer_text = request.form.get('answer_text_single_sq', '').strip()
            new_chapter_id_str = request.form.get('chapter_id_single_sq')

            if not new_chapter_id_str or not new_chapter_id_str.isdigit():
                flash('অবৈধ অধ্যায় নির্বাচন।', 'error_sq_single')
            elif not all([question_text, answer_text]):
                flash('অনুগ্রহ করে প্রশ্ন এবং উত্তর ঘর পূরণ করুন।', 'error_sq_single')
            else:
                new_chapter_id = int(new_chapter_id_str)
                cursor = conn.cursor()
                cursor.execute("UPDATE short_questions SET question_text = %s, answer_text = %s, chapter_id = %s WHERE id = %s",
                             (question_text, answer_text, new_chapter_id, sq_id))
                conn.commit()
                flash('সংক্ষিপ্ত প্রশ্ন সফলভাবে আপডেট করা হয়েছে!', 'success_sq_single')
                cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (new_chapter_id,)) # Get new subject_id
                updated_chapter_info = cursor.fetchone()
                updated_subject_id = updated_chapter_info[0] if updated_chapter_info else sq_item['subject_id']
                return redirect(url_for('manage.short_questions_list', subject_id=updated_subject_id, chapter_id=new_chapter_id))
        except (Exception, psycopg2.Error) as e:
            conn.rollback()
            current_app.logger.error(f"Error updating SQ {sq_id}: {e}")
            flash(f'সংক্ষিপ্ত প্রশ্ন আপডেট করতে সমস্যা হয়েছে: {e}', 'error_sq_single')
        finally:
            if cursor: cursor.close()

    subjects = get_subjects_for_manage_forms(conn)
    return render_template('admin/add_short_question.html', 
                           subjects=subjects, sq_data=sq_item, 
                           form_action=url_for('manage.edit_short_question', sq_id=sq_id), 
                           is_edit_mode=True)

@manage_bp.route('/short_questions/delete/<int:sq_id>', methods=['POST'])
@login_required
def delete_short_question(sq_id):
    conn = get_db()
    cursor = None
    original_chapter_id = None
    original_subject_id = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT sq.chapter_id, c.subject_id FROM short_questions sq JOIN chapters c ON sq.chapter_id = c.id WHERE sq.id = %s", (sq_id,))
        sq_info = cursor.fetchone()
        if sq_info:
            original_chapter_id = sq_info['chapter_id']
            original_subject_id = sq_info['subject_id']

        cursor.execute('DELETE FROM short_questions WHERE id = %s', (sq_id,))
        conn.commit()
        flash('সংক্ষিপ্ত প্রশ্ন সফলভাবে মুছে ফেলা হয়েছে!', 'success')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting SQ {sq_id}: {e}")
        flash(f'সংক্ষিপ্ত প্রশ্ন মুছতে সমস্যা হয়েছে: {e}', 'error')
    finally:
        if cursor: cursor.close()

    if original_subject_id and original_chapter_id:
        return redirect(url_for('manage.short_questions_list', subject_id=original_subject_id, chapter_id=original_chapter_id))
    return redirect(url_for('manage.short_questions_list'))


# --- Creative Question Management (List, Edit, Delete) ---
@manage_bp.route('/creative_questions', methods=['GET'])
@login_required
def creative_questions_list():
    conn = get_db()
    cursor = None
    subjects = get_subjects_for_manage_forms(conn)
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_chapter_id = request.args.get('chapter_id', type=int)
    chapters_for_selected_subject = []
    creative_questions_data = []

    try:
        if selected_subject_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT id, name FROM chapters WHERE subject_id = %s ORDER BY name", (selected_subject_id,))
            chapters_rows = cursor.fetchall()
            chapters_for_selected_subject = [dict(row) for row in chapters_rows]
            cursor.close()

        if selected_chapter_id:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT id, uddipak_text, question_ka FROM creative_questions WHERE chapter_id = %s ORDER BY id DESC", (selected_chapter_id,))
            cq_rows = cursor.fetchall()
            creative_questions_data = [dict(row) for row in cq_rows]
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error listing Creative Questions: {e}")
        flash("সৃজনশীল প্রশ্ন তালিকা আনতে সমস্যা হয়েছে।", "error")
    finally:
        if cursor: cursor.close()

    return render_template('admin/manage_creative_questions.html', 
                           subjects=subjects, 
                           selected_subject_id=selected_subject_id,
                           chapters_for_selected_subject=chapters_for_selected_subject,
                           selected_chapter_id=selected_chapter_id,
                           creative_questions=creative_questions_data)

@manage_bp.route('/creative_questions/edit/<int:cq_id>', methods=['GET', 'POST'])
@login_required
def edit_creative_question(cq_id):
    conn = get_db()
    cursor = None
    cq_item = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute('SELECT cq.*, ch.subject_id FROM creative_questions cq JOIN chapters ch ON cq.chapter_id = ch.id WHERE cq.id = %s', (cq_id,))
        cq_item_row = cursor.fetchone()
        if cq_item_row:
            cq_item = dict(cq_item_row)
    except (Exception, psycopg2.Error) as e:
        current_app.logger.error(f"Error fetching CQ {cq_id} for edit: {e}")
        flash("সৃজনশীল প্রশ্ন আনতে সমস্যা হয়েছে।", "error")
        return redirect(url_for('manage.creative_questions_list'))
    finally:
        if cursor: cursor.close()

    if not cq_item:
        flash('সৃজনশীল প্রশ্ন খুঁজে পাওয়া যায়নি।', 'error')
        return redirect(url_for('manage.creative_questions_list'))

    if request.method == 'POST':
        cursor = None
        try:
            uddipak_text = request.form.get('uddipak_text_single_cq', '').strip()
            question_ka = request.form.get('question_ka_single_cq', '').strip()
            answer_ka = request.form.get('answer_ka_single_cq', '').strip()
            question_kha = request.form.get('question_kha_single_cq', '').strip()
            answer_kha = request.form.get('answer_kha_single_cq', '').strip()
            question_ga = request.form.get('question_ga_single_cq', '').strip()
            answer_ga = request.form.get('answer_ga_single_cq', '').strip()
            question_gha = request.form.get('question_gha_single_cq', '').strip()
            answer_gha = request.form.get('answer_gha_single_cq', '').strip()
            new_chapter_id_str = request.form.get('chapter_id_single_cq')

            if not new_chapter_id_str or not new_chapter_id_str.isdigit():
                flash('অবৈধ অধ্যায় নির্বাচন।', 'error_cq_single')
            elif not all(str(request.form.get(f, "")).strip() for f in [
                'uddipak_text_single_cq', 'question_ka_single_cq', 'answer_ka_single_cq', 
                'question_kha_single_cq', 'answer_kha_single_cq', 'question_ga_single_cq', 
                'answer_ga_single_cq', 'question_gha_single_cq', 'answer_gha_single_cq']):
                flash('অনুগ্রহ করে সৃজনশীল প্রশ্নের সব ঘর পূরণ করুন।', 'error_cq_single')
            else:
                new_chapter_id = int(new_chapter_id_str)
                cursor = conn.cursor()
                cursor.execute("""UPDATE creative_questions SET uddipak_text=%s, question_ka=%s, answer_ka=%s, question_kha=%s, answer_kha=%s, 
                                question_ga=%s, answer_ga=%s, question_gha=%s, answer_gha=%s, chapter_id=%s WHERE id = %s""",
                             (uddipak_text, question_ka, answer_ka, question_kha, answer_kha, question_ga, answer_ga, question_gha, answer_gha, new_chapter_id, cq_id))
                conn.commit()
                flash('সৃজনশীল প্রশ্ন সফলভাবে আপডেট করা হয়েছে!', 'success_cq_single')
                cursor.execute("SELECT subject_id FROM chapters WHERE id = %s", (new_chapter_id,))
                updated_chapter_info = cursor.fetchone()
                updated_subject_id = updated_chapter_info[0] if updated_chapter_info else cq_item['subject_id']
                return redirect(url_for('manage.creative_questions_list', subject_id=updated_subject_id, chapter_id=new_chapter_id))
        except (Exception, psycopg2.Error) as e:
            conn.rollback()
            current_app.logger.error(f"Error updating CQ {cq_id}: {e}")
            flash(f'সৃজনশীল প্রশ্ন আপডেট করতে সমস্যা হয়েছে: {e}', 'error_cq_single')
        finally:
            if cursor: cursor.close()

    subjects = get_subjects_for_manage_forms(conn)
    return render_template('admin/add_creative_question.html', 
                           subjects=subjects, cq_data=cq_item, 
                           form_action=url_for('manage.edit_creative_question', cq_id=cq_id), 
                           is_edit_mode=True)

@manage_bp.route('/creative_questions/delete/<int:cq_id>', methods=['POST'])
@login_required
def delete_creative_question(cq_id):
    conn = get_db()
    cursor = None
    original_chapter_id = None
    original_subject_id = None
    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute("SELECT cq.chapter_id, ch.subject_id FROM creative_questions cq JOIN chapters ch ON cq.chapter_id = ch.id WHERE cq.id = %s", (cq_id,))
        cq_info = cursor.fetchone()
        if cq_info:
            original_chapter_id = cq_info['chapter_id']
            original_subject_id = cq_info['subject_id']

        cursor.execute('DELETE FROM creative_questions WHERE id = %s', (cq_id,))
        conn.commit()
        flash('সৃজনশীল প্রশ্ন সফলভাবে মুছে ফেলা হয়েছে!', 'success')
    except (Exception, psycopg2.Error) as e:
        conn.rollback()
        current_app.logger.error(f"Error deleting CQ {cq_id}: {e}")
        flash(f'সৃজনশীল প্রশ্ন মুছতে সমস্যা হয়েছে: {e}', 'error')
    finally:
        if cursor: cursor.close()

    if original_subject_id and original_chapter_id:
        return redirect(url_for('manage.creative_questions_list', subject_id=original_subject_id, chapter_id=original_chapter_id))
    return redirect(url_for('manage.creative_questions_list'))