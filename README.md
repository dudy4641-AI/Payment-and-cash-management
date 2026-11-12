# ניהול תשלומי ספקים ויתרות

האפיון ב-`SPEC.md`, התוכנית ב-`PLAN.md`, הנתונים המדומים והתוצאות הצפויות ב-`docs/MOCK_DATA.md`.

## הרצת המסך

```bash
pip install -r requirements.txt
streamlit run app.py
```

בלי הגדרות, כל דפדפן מקבל חברת הדגמה משלו בזיכרון. כדי לעבוד מול סופאבייס, מגדירים `SUPABASE_URL` ו-`SUPABASE_KEY` (המפתח הסודי של הפרויקט) כמשתני סביבה או ב-`.streamlit/secrets.toml`, ומריצים קודם את כל הקבצים ב-`supabase/migrations` לפי הסדר.

## בדיקות

```bash
python3 -m pytest
```

בדיקות סופאבייס רצות רק כש-`SUPABASE_URL` מוגדר. בדיקת האחסון מוחקת את כל הנתונים בפרויקט, ולכן רק מול פרויקט הבדיקות.
