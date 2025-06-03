# quiz_app/config.py
import os

class Config:
    """Flask অ্যাপ্লিকেশন কনফিগারেশন ক্লাস।"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'e5a9f807a8c7f8d9e0f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8_pg' # প্রয়োজনে পরিবর্তন করুন

    # PostgreSQL ডাটাবেসের কানেকশন URI
    # আপনার দেওয়া URI টি এখানে ব্যবহার করুন
    POSTGRES_URI = os.environ.get('DATABASE_URL') or "postgresql://paathshala_user:MGJKo8bn0WvAHjn4v2twe4nDO4d8bEf4@dpg-d0vbdpnfte5s739flk4g-a/paathshala"

    DEBUG = True # ডেভেলপমেন্টের জন্য True, প্রোডাকশনে False করে দিন
