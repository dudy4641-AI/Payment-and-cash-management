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

## פרסום ב-Streamlit Community Cloud

נכנסים ל-share.streamlit.io, מתחברים עם GitHub ובוחרים Create app, ואז Deploy a public app from GitHub:

| שדה | ערך |
|---|---|
| Repository | `dudy4641-AI/Payment-and-cash-management` |
| Branch | `claude/eloquent-maxwell-jc97g1` (או `main` אחרי מיזוג) |
| Main file path | `app.py` |
| App URL | שם לבחירתכם, למשל `supplier-payments` |
| Advanced settings → Python version | 3.12 ומעלה |
| Advanced settings → Secrets | ריק, למצב הדגמה |

בלי סודות, כל מבקר מקבל חברת הדגמה משלו בזיכרון, וזה לא נוגע בסופאבייס.

כדי לעבוד מול סופאבייס, ממלאים ב-Secrets:

```toml
SUPABASE_URL = "https://<project-ref>.supabase.co"
SUPABASE_KEY = "<המפתח הסודי של הפרויקט>"
```

זהירות: עם המפתח הסודי, כל מי שיש לו את הקישור יכול לקרוא ולשנות את כל הנתונים בפרויקט. אם מגדירים סודות, צריך להפוך את האפליקציה לפרטית (Settings → Sharing → Only specific people can view this app) ולהזמין רק את מי שצריך.
