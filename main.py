# quiz_app/app.py
from flask import Flask, g, session, current_app as app_context
import os

# মডিউলগুলো ইম্পোর্ট করুন
import database
import auth
import public_routes 
import admin_routes  
import manage_routes 

def create_app(config_name='config.Config'):
    app = Flask(__name__)

    from config import Config as AppConfig
    app.config.from_object(AppConfig)

    # ডাটাবেস ইনিশিয়ালাইজ করুন (টেবিল তৈরি)
    with app.app_context(): # init_db_on_startup এ current_app ব্যবহারের জন্য
        database.init_db_on_startup() 

    database.init_app_db(app) # teardown context রেজিস্টার করার জন্য

    @app.before_request
    def load_user_from_session():
        user_id = session.get('user_id')
        g.user = None
        if user_id is not None:
            db_conn = None # কানেকশন ভেরিয়েবল
            cursor = None  # কার্সার ভেরিয়েবল
            try:
                db_conn = database.get_db() 
                # psycopg2.extras.DictCursor ব্যবহার করতে হলে কার্সার সেভাবে তৈরি করতে হবে
                from psycopg2.extras import DictCursor
                cursor = db_conn.cursor(cursor_factory=DictCursor)
                cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
                g.user = cursor.fetchone()
            except Exception as e:
                app_context.logger.error(f"Failed to load user from session: {e}")
                g.user = None
            finally:
                if cursor: cursor.close()
                # get_db() থেকে পাওয়া কানেকশনটি close_db() দ্বারা বন্ধ হবে, এখানে বন্ধ করার দরকার নেই।

    @app.context_processor
    def inject_user():
        return dict(g_user=getattr(g, 'user', None))

    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(public_routes.public_bp)
    app.register_blueprint(admin_routes.admin_bp)
    app.register_blueprint(manage_routes.manage_bp)

    return app

if __name__ == '__main__':
    app_instance = create_app()
    app_instance.run(debug=app_instance.config.get('DEBUG', True), host='0.0.0.0', port=5000)