import os
from datetime import datetime
from functools import wraps
from io import BytesIO
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, abort
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deploy")
database_url = os.environ.get("DATABASE_URL", "sqlite:///student_portal.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
db = SQLAlchemy(app)
ALLOWED = {"pdf","doc","docx","ppt","pptx","txt","png","jpg","jpeg"}

class User(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(100), nullable=False)
    email=db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash=db.Column(db.String(255), nullable=False)
    role=db.Column(db.String(20), default="student", nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Material(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    title=db.Column(db.String(160), nullable=False)
    description=db.Column(db.String(500), default="")
    filename=db.Column(db.String(255), nullable=False)
    content_type=db.Column(db.String(100), default="application/octet-stream")
    data=db.Column(db.LargeBinary, nullable=False)
    uploaded_by=db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Question(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    question=db.Column(db.String(500), nullable=False)
    option_a=db.Column(db.String(250), nullable=False)
    option_b=db.Column(db.String(250), nullable=False)
    option_c=db.Column(db.String(250), nullable=False)
    option_d=db.Column(db.String(250), nullable=False)
    correct=db.Column(db.String(1), nullable=False)
    explanation=db.Column(db.String(500), default="")

class ExamAttempt(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    user_id=db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score=db.Column(db.Integer, nullable=False)
    total=db.Column(db.Integer, nullable=False)
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

class Notice(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    title=db.Column(db.String(180), nullable=False)
    category=db.Column(db.String(40), default="General")
    body=db.Column(db.Text, nullable=False)
    link=db.Column(db.String(500), default="")
    created_at=db.Column(db.DateTime, default=datetime.utcnow)

def current_user():
    return db.session.get(User, session.get("user_id")) if session.get("user_id") else None

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        u=current_user()
        if not u or u.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def home():
    return render_template("home.html",
        notices=Notice.query.order_by(Notice.created_at.desc()).limit(5).all(),
        materials=Material.query.order_by(Material.created_at.desc()).limit(6).all())

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        name=request.form.get("name","").strip()
        email=request.form.get("email","").strip().lower()
        password=request.form.get("password","")
        if not name or not email or len(password)<8:
            flash("Name, email and password (minimum 8 characters) are required.","danger")
        elif User.query.filter_by(email=email).first():
            flash("This email is already registered.","warning")
        else:
            db.session.add(User(name=name,email=email,password_hash=generate_password_hash(password)))
            db.session.commit()
            flash("Registration successful. Please login.","success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if u and check_password_hash(u.password_hash,request.form.get("password","")):
            session.clear(); session["user_id"]=u.id
            return redirect(url_for("admin_dashboard" if u.role=="admin" else "dashboard"))
        flash("Invalid email or password.","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); flash("Logged out.","info"); return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    attempts=ExamAttempt.query.filter_by(user_id=current_user().id).order_by(ExamAttempt.created_at.desc()).limit(5).all()
    return render_template("dashboard.html",attempts=attempts)

@app.route("/materials")
def materials():
    return render_template("materials.html",materials=Material.query.order_by(Material.created_at.desc()).all())

@app.route("/materials/<int:item_id>/download")
def download_material(item_id):
    item=db.session.get(Material,item_id)
    if not item: abort(404)
    return send_file(BytesIO(item.data),mimetype=item.content_type,as_attachment=True,download_name=item.filename)

@app.route("/exam")
@login_required
def exam():
    return render_template("exam.html",questions=Question.query.order_by(Question.id.asc()).all())

@app.route("/exam/submit",methods=["POST"])
@login_required
def submit_exam():
    qs=Question.query.order_by(Question.id.asc()).all()
    if not qs:
        flash("No exam questions yet.","warning"); return redirect(url_for("exam"))
    score=sum(1 for q in qs if request.form.get(str(q.id),"").upper()==q.correct)
    db.session.add(ExamAttempt(user_id=current_user().id,score=score,total=len(qs))); db.session.commit()
    return render_template("exam_result.html",score=score,total=len(qs))

@app.route("/notices")
def notices():
    return render_template("notices.html",notices=Notice.query.order_by(Notice.created_at.desc()).all())

@app.route("/admin")
@admin_required
def admin_dashboard():
    return render_template("admin.html",users=User.query.all(),materials=Material.query.all(),
        questions=Question.query.all(),notices=Notice.query.order_by(Notice.created_at.desc()).all(),
        attempts=ExamAttempt.query.count())

@app.route("/admin/materials/add",methods=["POST"])
@admin_required
def add_material():
    title=request.form.get("title","").strip(); upload=request.files.get("file")
    if not title or not upload or not upload.filename:
        flash("Title and file are required.","danger")
    elif "." not in upload.filename or upload.filename.rsplit(".",1)[1].lower() not in ALLOWED:
        flash("Unsupported file type.","danger")
    else:
        raw=upload.read()
        if len(raw)>10*1024*1024: flash("File exceeds 10 MB.","danger")
        else:
            db.session.add(Material(title=title,description=request.form.get("description","").strip(),
                filename=secure_filename(upload.filename),content_type=upload.mimetype or "application/octet-stream",
                data=raw,uploaded_by=current_user().id))
            db.session.commit(); flash("Material uploaded.","success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/materials/<int:item_id>/delete",methods=["POST"])
@admin_required
def delete_material(item_id):
    item=db.session.get(Material,item_id)
    if item: db.session.delete(item); db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/questions/add",methods=["POST"])
@admin_required
def add_question():
    keys=["question","option_a","option_b","option_c","option_d"]
    vals={k:request.form.get(k,"").strip() for k in keys}
    correct=request.form.get("correct","").upper()
    if not all(vals.values()) or correct not in {"A","B","C","D"}:
        flash("Complete all question fields.","danger")
    else:
        db.session.add(Question(**vals,correct=correct,explanation=request.form.get("explanation","").strip()))
        db.session.commit(); flash("Question added.","success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/questions/<int:item_id>/delete",methods=["POST"])
@admin_required
def delete_question(item_id):
    item=db.session.get(Question,item_id)
    if item: db.session.delete(item); db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/notices/add",methods=["POST"])
@admin_required
def add_notice():
    title=request.form.get("title","").strip(); body=request.form.get("body","").strip()
    if not title or not body: flash("Title and notice details are required.","danger")
    else:
        db.session.add(Notice(title=title,body=body,category=request.form.get("category","General"),
            link=request.form.get("link","").strip()))
        db.session.commit(); flash("Notice published.","success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/notices/<int:item_id>/delete",methods=["POST"])
@admin_required
def delete_notice(item_id):
    item=db.session.get(Notice,item_id)
    if item: db.session.delete(item); db.session.commit()
    return redirect(url_for("admin_dashboard"))

@app.route("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status":"ok","database":"connected"},200
    except Exception:
        return {"status":"error","database":"unavailable"},503

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="admin").first():
        db.session.add(User(name="Portal Admin",
            email=os.environ.get("ADMIN_EMAIL","admin@studentportal.local").strip().lower(),
            password_hash=generate_password_hash(os.environ.get("ADMIN_PASSWORD","ChangeMe123!")),role="admin"))
        db.session.commit()

if __name__=="__main__":
    app.run(host="127.0.0.1",port=int(os.environ.get("PORT",5000)),debug=False)
