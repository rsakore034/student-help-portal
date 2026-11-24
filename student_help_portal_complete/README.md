# Student Help Portal

## Local Windows setup
1. Install Python 3.11/3.12.
2. Extract this ZIP and open PowerShell in this folder.
3. Run:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   $env:SECRET_KEY="use-a-long-random-secret"
   $env:ADMIN_EMAIL="your-email@example.com"
   $env:ADMIN_PASSWORD="UseYourOwnStrongPassword"
   $env:DATABASE_URL="sqlite:///student_portal.db"
   python app.py
   ```
4. Open http://127.0.0.1:5000

## Supabase database
1. Create a project at https://supabase.com.
2. Open Project Settings -> Database -> Connection string -> URI.
3. Copy the PostgreSQL connection string, replace the password placeholder and keep it private.
4. For Render, add it as environment variable `DATABASE_URL`. The app supports PostgreSQL via psycopg.

## GitHub and Render deployment
1. Create a GitHub repository and upload all files from this folder. Do not upload passwords, `.env`, or database secrets.
2. In Render, choose New -> Web Service and connect that repository.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app`
5. Add environment variables:
   - `SECRET_KEY`: long random secret
   - `DATABASE_URL`: Supabase PostgreSQL URI
   - `ADMIN_EMAIL`: your admin email
   - `ADMIN_PASSWORD`: a unique strong password
6. Deploy and open the `onrender.com` URL. Test `/health`.

## Notes
- Admin account is created on first database initialization only. Changing ADMIN_PASSWORD later does not reset an existing admin.
- Default local admin only if you did not set environment variables: `admin@studentportal.local` / `ChangeMe123!`. Change it before use.
- Uploads are stored as binary data in PostgreSQL (10 MB per file), not Render's temporary filesystem.
- Render Free web services sleep after 15 minutes without requests and wake on the next visit. Supabase Free projects may pause after a week of low database activity. Check current plan limits.
- This starter is for learning/small pilots. Before public school-wide use, add email verification, password reset, CSRF protection, rate limiting, backups and privacy review.
