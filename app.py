from flask import Flask, render_template, send_from_directory, request, redirect, url_for, session, send_file, \
    make_response
import os
import io
import csv
import base64
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

# Change these two lines before real use
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin')

# Database connection
DATABASE_URL = os.environ.get('DATABASE_URL')


def get_db_connection():
    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        import psycopg2
        # Render uses 'postgres://' but psycopg2 needs 'postgresql://'
        url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(url, sslmode='require')
        return conn
    else:
        # Fallback to SQLite for local development
        import sqlite3
        return sqlite3.connect('roster.db')


def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        # PostgreSQL syntax
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id SERIAL PRIMARY KEY, 
                      name TEXT, 
                      position TEXT, 
                      dob TEXT, 
                      height TEXT, 
                      place_birth TEXT, 
                      photo BYTEA)''')
    else:
        # SQLite syntax
        c.execute('''CREATE TABLE IF NOT EXISTS players
                     (id INTEGER PRIMARY KEY, 
                      name TEXT, 
                      position TEXT, 
                      dob TEXT, 
                      height TEXT, 
                      place_birth TEXT, 
                      photo BLOB)''')
    conn.commit()
    conn.close()


init_db()


def login_required(f):
    def wrap(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    wrap.__name__ = f.__name__
    return wrap


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        return render_template('login.html', error="Wrong credentials")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)


@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, position, dob, height, place_birth, photo FROM players")
    rows = c.fetchall()
    players = []
    for r in rows:
        photo_b64 = None
        if r[6]:
            # Handle both SQLite (buffer) and PostgreSQL (memoryview/bytes)
            photo_bytes = bytes(r[6]) if isinstance(r[6], memoryview) else r[6]
            photo_b64 = base64.b64encode(photo_bytes).decode()
        players.append((r[0], r[1], r[2], r[3], r[4], r[5], photo_b64))
    conn.close()
    return render_template('dashboard.html', players=players)


@app.route('/admin')
@login_required
def admin():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, position, dob, height, place_birth, photo FROM players")
    rows = c.fetchall()
    players = []
    for r in rows:
        photo_b64 = None
        if r[6]:
            photo_bytes = bytes(r[6]) if isinstance(r[6], memoryview) else r[6]
            photo_b64 = base64.b64encode(photo_bytes).decode()
        players.append((r[0], r[1], r[2], r[3], r[4], r[5], photo_b64))
    conn.close()
    return render_template('admin.html', players=players)


@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        dob = request.form['dob']
        height = request.form['height']
        place_birth = request.form['place_birth']
        photo = request.files.get('photo')
        photo_data = photo.read() if photo and photo.filename else None

        conn = get_db_connection()
        c = conn.cursor()

        if DATABASE_URL and DATABASE_URL.startswith('postgres'):
            # PostgreSQL uses %s placeholders
            c.execute(
                "INSERT INTO players (name, position, dob, height, place_birth, photo) VALUES (%s,%s,%s,%s,%s,%s)",
                (name, position, dob, height, place_birth, photo_data))
        else:
            # SQLite uses ? placeholders
            c.execute("INSERT INTO players (name, position, dob, height, place_birth, photo) VALUES (?,?,?,?,?,?)",
                      (name, position, dob, height, place_birth, photo_data))

        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))
    return render_template('add.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db_connection()
    c = conn.cursor()

    if request.method == 'POST':
        name = request.form['name']
        position = request.form['position']
        dob = request.form['dob']
        height = request.form['height']
        place_birth = request.form['place_birth']
        photo = request.files.get('photo')
        photo_data = photo.read() if photo and photo.filename else None

        if DATABASE_URL and DATABASE_URL.startswith('postgres'):
            if photo_data:
                c.execute("UPDATE players SET name=%s,position=%s,dob=%s,height=%s,place_birth=%s,photo=%s WHERE id=%s",
                          (name, position, dob, height, place_birth, photo_data, id))
            else:
                c.execute("UPDATE players SET name=%s,position=%s,dob=%s,height=%s,place_birth=%s WHERE id=%s",
                          (name, position, dob, height, place_birth, id))
        else:
            if photo_data:
                c.execute("UPDATE players SET name=?,position=?,dob=?,height=?,place_birth=?,photo=? WHERE id=?",
                          (name, position, dob, height, place_birth, photo_data, id))
            else:
                c.execute("UPDATE players SET name=?,position=?,dob=?,height=?,place_birth=? WHERE id=?",
                          (name, position, dob, height, place_birth, id))

        conn.commit()
        conn.close()
        return redirect(url_for('admin'))

    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        c.execute("SELECT name,position,dob,height,place_birth FROM players WHERE id=%s", (id,))
    else:
        c.execute("SELECT name,position,dob,height,place_birth FROM players WHERE id=?", (id,))

    player = c.fetchone()
    conn.close()
    return render_template('edit.html', player=player, id=id)


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    conn = get_db_connection()
    c = conn.cursor()

    if DATABASE_URL and DATABASE_URL.startswith('postgres'):
        c.execute("DELETE FROM players WHERE id=%s", (id,))
    else:
        c.execute("DELETE FROM players WHERE id=?", (id,))

    conn.commit()
    conn.close()
    return redirect(url_for('admin'))


@app.route('/download_roster')
@login_required
def download_roster():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, position, dob, height, place_birth FROM players")
    rows = c.fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Position', 'DOB', 'Height', 'Place of Birth'])
    writer.writerows(rows)

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='reno_roster.csv'
    )


@app.route('/download_pdf')
@login_required
def download_pdf():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, position, dob, height, place_birth, photo FROM players")
    players = c.fetchall()
    conn.close()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30,
                            bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph("RENO Roster - Player List", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3 * inch))

    data = [['Photo', 'Name', 'Position', 'DOB', 'Height', 'Place of Birth']]

    for player in players:
        name, pos, dob, height, pob, photo_blob = player
        if photo_blob:
            # Handle both SQLite and PostgreSQL binary data
            photo_bytes = bytes(photo_blob) if isinstance(photo_blob, memoryview) else photo_blob
            img_buffer = io.BytesIO(photo_bytes)
            try:
                img = Image(img_buffer, width=0.8 * inch, height=0.8 * inch)
            except:
                img = Paragraph("No Image", styles['Normal'])
        else:
            img = Paragraph("No Image", styles['Normal'])

        data.append([img, name or "", pos or "", dob or "", height or "", pob or ""])

    table = Table(data, colWidths=[1.2 * inch, 2 * inch, 1.5 * inch, 1.2 * inch, 1.2 * inch, 2.5 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
    ]))

    elements.append(table)

    doc.build(elements)
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=reno_roster.pdf'
    return response


@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('static/'):
        return send_from_directory('static', path[7:])
    return "Not Found", 404


if __name__ == '__main__':
    app.run()