from flask import Flask, render_template, request, redirect, url_for, session, jsonify, g
from werkzeug.security import check_password_hash, generate_password_hash
from markupsafe import Markup
import os

from auth import authLog
from config import sqliteConfig
from modules import docxtohtml

app = Flask(__name__)
app.secret_key = '4f3d6e9a5f4b1c8d7e6a2b3c9d0e8f1a5b7c2d4e6f9a1b3c8d0e6f2a9b1d3c4'

DOCUMENTS_DIR = 'documents'

@app.route('/')
@app.route('/home')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard', user=session['username'], role=session.get('role')))
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/section/<section_name>')
def section(section_name):
    section_path = os.path.join(DOCUMENTS_DIR, section_name)

    if not os.path.isdir(section_path):
        return f"Section '{section_name}' not found", 404

    # Get .docx file names without extension
    files = [f[:-5] for f in os.listdir(section_path) if f.endswith('.docx')]

    return render_template('dashboard.html', section=section_name, files=files)

@app.route('/docs/<section>/<filename>')
def view_docx(section, filename):
    docxtohtml.clear_temp_images()  # 💥 Clear previously extracted images

    section_path = os.path.join(DOCUMENTS_DIR, section)
    filepath = os.path.join(section_path, f"{filename}.docx")

    if not os.path.exists(filepath):
        return f"<h3>Document '{filename}.docx' not found in '{section}'</h3>"

    files = [f[:-5] for f in os.listdir(section_path) if f.endswith('.docx')]

    # 🧠 Split filename format: name_version_date
    parts = filename.rsplit('_', 2)  # limit splits to preserve underscores in name
    doc_name = parts[0] if len(parts) > 0 else filename
    version = parts[1] if len(parts) > 1 else ""
    date = parts[2] if len(parts) > 2 else ""

    html_content, toc_html = docxtohtml.docx_to_html(filepath)

    return render_template(
        'docviewer.html',
        content=Markup(html_content),
        toc=Markup(toc_html),
        section=section,
        files=files,
        active_file=filename,
        doc_name=doc_name,
        version=version,
        date=date
    )

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    user = authLog.get_user(username)
    if user and check_password_hash(user[2], password):
        session.permanent = True
        session['username'] = user[1]
        session['role'] = user[3]
        session['user_logs'] = []
        return jsonify(success=True)
    else:
        return jsonify(success=False, error="Invalid Credentials"), 403

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return jsonify(success=False, error="Not logged in"), 403

    data = request.get_json()
    old_password = data.get('oldPassword')
    new_password = data.get('newPassword')

    username = session['username']

    conn = sqliteConfig.get_db_connection()
    if conn is None:
        return jsonify(success=False, error="Database connection error"), 500

    try:
        cur = conn.cursor()
        # Fetch the stored password hash
        cur.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
        row = cur.fetchone()

        if not row:
            return jsonify(success=False, error="User not found"), 404

        stored_password_hash = row[0]

        if check_password_hash(stored_password_hash, old_password):
            # If old password matches, update with new password
            new_password_hash = generate_password_hash(new_password)

            cur.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_password_hash, username))
            conn.commit()

            return jsonify(success=True)
        else:
            return jsonify(success=False, error="Old password is incorrect."), 400

    except Exception as e:
        print("Error during password change:", e)
        return jsonify(success=False, error=str(e)), 500

    finally:
        cur.close()
        conn.close()

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.before_request
def load_user():
    g.user = session.get('username')
    g.role = session.get('role')

@app.context_processor
def inject_user():
    sections = []
    try:
        documents_path = DOCUMENTS_DIR
        sections = [
            name for name in os.listdir(documents_path)
            if os.path.isdir(os.path.join(documents_path, name))
        ]
    except Exception as e:
        print(f"Error loading sections: {e}")
    return dict(
        user=session.get('username'),
        role=session.get('role'),
        section_list=sections  # 👈 Inject section list globally
    )

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)