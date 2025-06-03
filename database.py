# quiz_app/database.py
import psycopg2
import psycopg2.extras # DictCursor ব্যবহারের জন্য
import os
from flask import g, current_app

def get_db_uri():
    """অ্যাপ্লিকেশন কনফিগারেশন থেকে ডাটাবেস URI আনে।"""
    try:
        return current_app.config['POSTGRES_URI']
    except RuntimeError: # App context এর বাইরে কল হলে (যেমন init_db_on_startup)
        # config.py থেকে সরাসরি লোড করার চেষ্টা করা যেতে পারে, অথবা একটি ডিফল্ট URI দিন
        # এই উদাহরণে, আমরা একটি ডিফল্ট এনভায়রনমেন্ট ভেরিয়েবল থেকে নেওয়ার চেষ্টা করছি
        # অথবা হার্ডকোড করা যেতে পারে (তবে এটি প্রস্তাবিত নয়)
        return os.environ.get('DATABASE_URL_INIT') or "postgresql://unknown_t0fx_user:ZAG3RGEpGXuVXTP5MjyuZJU6a4VeXykU@dpg-d0upmpjipnbc73eptrbg-a.singapore-postgres.render.com/unknown_t0fx"


def init_db_on_startup():
    """
    PostgreSQL ডাটাবেসে প্রয়োজনীয় টেবিল তৈরি করে (যদি না থাকে)।
    অ্যাপ্লিকেশন চালু হওয়ার সময় এটি কল করা হবে।
    """
    db_uri = get_db_uri()
    conn = None
    try:
        conn = psycopg2.connect(dsn=db_uri)
        cursor = conn.cursor()

        # PostgreSQL এ ফরেন কী ডিফল্টরূপে চালু থাকে যদি সঠিকভাবে ডিফাইন করা হয়, PRAGMA প্রয়োজন নেই

        # Subjects Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        ''')

        # Chapters Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chapters (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                UNIQUE (subject_id, name)
            )
        ''')

        # Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # MCQ Questions Table (named 'questions')
        # PostgreSQL এ টেবিল চেক করার পদ্ধতি ভিন্ন, তবে CREATE TABLE IF NOT EXISTS যথেষ্ট
        # কলামের পরিবর্তন (যেমন chapter_id যোগ) সঠিকভাবে করার জন্য ম্যানুয়াল মাইগ্রেশন বা ALTER TABLE প্রয়োজন হতে পারে
        # এই উদাহরণে, আমরা ধরে নিচ্ছি টেবিলটি নতুনভাবে তৈরি হচ্ছে অথবা ইতিমধ্যে সঠিক গঠনে আছে
        cursor.execute("DROP TABLE IF EXISTS questions CASCADE") # পুরানো SQLite টেবিল থাকলে সমস্যা এড়াতে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id SERIAL PRIMARY KEY,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL CHECK(correct_option IN ('a', 'b', 'c', 'd')),
                chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE
            )
        ''')

        # Short Questions Table
        cursor.execute("DROP TABLE IF EXISTS short_questions CASCADE") # পুরানো টেবিল থাকলে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS short_questions (
                id SERIAL PRIMARY KEY,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE
            )
        ''')

        # User Seen Short Questions Table
        cursor.execute("DROP TABLE IF EXISTS user_seen_short_questions CASCADE") # পুরানো টেবিল থাকলে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_seen_short_questions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                short_question_id INTEGER NOT NULL REFERENCES short_questions(id) ON DELETE CASCADE,
                seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, short_question_id)
            )
        ''')

        # Creative Questions Table
        cursor.execute("DROP TABLE IF EXISTS creative_questions CASCADE") # পুরানো টেবিল থাকলে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS creative_questions (
                id SERIAL PRIMARY KEY,
                uddipak_text TEXT NOT NULL,
                question_ka TEXT NOT NULL,
                answer_ka TEXT NOT NULL,
                question_kha TEXT NOT NULL,
                answer_kha TEXT NOT NULL,
                question_ga TEXT NOT NULL,
                answer_ga TEXT NOT NULL,
                question_gha TEXT NOT NULL,
                answer_gha TEXT NOT NULL,
                chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE
            )
        ''')

        # User Seen Creative Questions Table
        cursor.execute("DROP TABLE IF EXISTS user_seen_creative_questions CASCADE") # পুরানো টেবিল থাকলে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_seen_creative_questions (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                creative_question_id INTEGER NOT NULL REFERENCES creative_questions(id) ON DELETE CASCADE,
                seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, creative_question_id)
            )
        ''')

        # User Attempted MCQs Table
        cursor.execute("DROP TABLE IF EXISTS user_attempted_mcqs CASCADE") # পুরানো টেবিল থাকলে (ডেটা মুছে যাবে!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_attempted_mcqs (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                mcq_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE, 
                attempted_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, mcq_id)
            )
        ''')

        conn.commit()
        cursor.close()
        print(f"PostgreSQL Database schema checked/initialized successfully using URI: {db_uri.split('@')[-1]}.") # URI এর সংবেদনশীল অংশ বাদ দিয়ে লগ
    except (Exception, psycopg2.Error) as error:
        print(f"Error while connecting to PostgreSQL or initializing schema: {error}")
    finally:
        if conn:
            conn.close()

def get_db():
    """
    বর্তমান অ্যাপ্লিকেশন কনটেক্সটের জন্য একটি PostgreSQL ডাটাবেস কানেকশন প্রদান করে।
    psycopg2.extras.DictCursor ব্যবহার করে কলামের নাম দিয়ে ডেটা অ্যাক্সেস করার সুবিধা দেয়।
    """
    db_uri = current_app.config['POSTGRES_URI']
    if 'db' not in g:
        try:
            g.db = psycopg2.connect(dsn=db_uri)
        except psycopg2.OperationalError as e:
            current_app.logger.error(f"Failed to connect to PostgreSQL: {e}")
            # এখানে একটি কাস্টম এরর পেজ দেখানো যেতে পারে অথবা অ্যাপ ক্র্যাশ করতে পারে
            # আপাতত এরর রেইজ করছি, যা Flask এর ডিফল্ট এরর হ্যান্ডলার ধরবে
            raise ConnectionError(f"Could not connect to the database: {e}") from e
    return g.db # এটি কানেকশন অবজেক্ট

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_app_db(app):
    app.teardown_appcontext(close_db)