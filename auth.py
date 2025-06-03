# quiz_app/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import get_db 
import psycopg2 # psycopg2 এরর ধরার জন্য
import psycopg2.extras # DictCursor এর জন্য

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            flash('এই পৃষ্ঠা দেখতে অনুগ্রহ করে লগইন করুন।', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return view(**kwargs)
    return wrapped_view

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if g.user: 
        return redirect(url_for('public.main_homepage')) # public blueprint

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        error = None

        if not username: error = 'ইউজারনেম আবশ্যক।'
        elif not password: error = 'পাসওয়ার্ড আবশ্যক।'
        elif len(password) < 6: error = 'পাসওয়ার্ড কমপক্ষে ৬ অক্ষরের হতে হবে।'
        elif password != confirm_password: error = 'পাসওয়ার্ড দুটি মিলছে না।'

        if error is None:
            db = get_db()
            cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor) # DictCursor ব্যবহার
            try:
                cursor.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email if email else None, generate_password_hash(password)),
                )
                db.commit()
            except psycopg2.errors.UniqueViolation: # PostgreSQL এর জন্য নির্দিষ্ট এরর
                error = f"ইউজারনেম '{username}' অথবা ইমেইল '{email}' ইতিমধ্যে ব্যবহৃত হয়েছে।"
            except (psycopg2.Error, Exception) as e:
                db.rollback()
                current_app.logger.error(f"Registration error for {username}: {e}")
                error = f"একটি অপ্রত্যাশিত ত্রুটি ঘটেছে: {e}"
            else:
                flash('নিবন্ধন সফল হয়েছে! অনুগ্রহ করে লগইন করুন।', 'success')
                cursor.close()
                return redirect(url_for('auth.login'))
            finally:
                if cursor: cursor.close()

        if error: flash(error, 'error')
    return render_template('auth/register.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('public.main_homepage')) # public blueprint

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password')
        db = get_db()
        cursor = db.cursor(cursor_factory=psycopg2.extras.DictCursor) # DictCursor ব্যবহার
        error = None
        user = None
        try:
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
        except (psycopg2.Error, Exception) as e:
            current_app.logger.error(f"Login DB error for {username}: {e}")
            error = "লগইন করার সময় একটি সমস্যা হয়েছে।"
        finally:
            if cursor: cursor.close()

        if user is None and not error:
            error = 'ভুল ইউজারনেম অথবা পাসওয়ার্ড।'
        elif user and not check_password_hash(user['password_hash'], password): # user এখানে DictRow
            error = 'ভুল ইউজারনেম অথবা পাসওয়ার্ড।'

        if error is None and user:
            session.clear()
            session['user_id'] = user['id']
            flash('সফলভাবে লগইন করেছেন!', 'success')
            next_page = request.args.get('next')
            if next_page: return redirect(next_page)
            return redirect(url_for('public.main_homepage'))

        if error: flash(error, 'error')
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required 
def logout():
    session.clear()
    g.user = None 
    flash('আপনি সফলভাবে লগআউট করেছেন।', 'info')
    return redirect(url_for('public.main_homepage')) # public blueprint