import os
import json
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify, session, redirect, url_for, send_from_directory
from flask_cors import CORS
from datetime import datetime
from functools import wraps

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your-secret-key-here-change-in-production'
CORS(app)

# Configuration
STUDENTS_FILE = 'students.csv'
ATTENDANCE_FILE = 'attendance.csv'
MIN_FACE_CONFIDENCE = 0.6

# Authentication Passwords
ADMIN_PASSWORD = 'admin123'  # Admin password - Change in production
# Students use face recognition for login (no password needed)

# Attendance time window (set to None to disable restriction)
ATTENDANCE_START_TIME = None  # Example: '09:00' for 9 AM
ATTENDANCE_END_TIME = None     # Example: '10:00' for 10 AM
LATE_THRESHOLD = None          # Example: '09:30' - mark as late after this time

# Initialize files
def init_students_file():
    if not os.path.exists(STUDENTS_FILE):
        df = pd.DataFrame(columns=["student_id", "name", "department", "semester", "face_descriptor"])
        df.to_csv(STUDENTS_FILE, index=False)

def init_attendance_file():
    if not os.path.exists(ATTENDANCE_FILE):
        df = pd.DataFrame(columns=["student_id", "name", "department", "date", "time", "status"])
        df.to_csv(ATTENDANCE_FILE, index=False)

# Load students database
def load_students_db():
    try:
        if os.path.exists(STUDENTS_FILE):
            df = pd.read_csv(STUDENTS_FILE)
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error loading students: {e}")
        return pd.DataFrame()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session and 'is_admin' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'is_admin' not in session or not session['is_admin']:
            return redirect('/admin-login')
        return f(*args, **kwargs)
    return decorated_function

# Check if attendance already marked today
def is_attendance_marked_today(student_id):
    try:
        if not os.path.exists(ATTENDANCE_FILE):
            return False
        df = pd.read_csv(ATTENDANCE_FILE)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Check if student has attendance for today
        # Convert student_id column and input to string for comparison
        df['student_id'] = df['student_id'].astype(str)
        today_attendance = df[(df['student_id'] == str(student_id)) & (df['date'] == today)]
        return len(today_attendance) > 0
    except Exception as e:
        print(f"Error checking attendance: {e}")
        return False

# Check if current time is within attendance window
def is_within_attendance_window():
    if ATTENDANCE_START_TIME is None or ATTENDANCE_END_TIME is None:
        return {"allowed": True, "status": "Present"}  # No restriction
    
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    if current_time < ATTENDANCE_START_TIME:
        return {"allowed": False, "message": f"Attendance window opens at {ATTENDANCE_START_TIME}"}
    elif current_time > ATTENDANCE_END_TIME:
        return {"allowed": False, "message": f"Attendance window closed at {ATTENDANCE_END_TIME}"}
    elif LATE_THRESHOLD and current_time > LATE_THRESHOLD:
        return {"allowed": True, "status": "Late"}
    else:
        return {"allowed": True, "status": "Present"}

# Mark attendance
def mark_student_attendance(student_id, student_name, department):
    try:
        # Check time window
        time_check = is_within_attendance_window()
        if not time_check["allowed"]:
            return {"success": False, "message": time_check["message"]}
        
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%I:%M:%S %p")  # 12-hour format with AM/PM
        status = time_check.get("status", "Present")
        
        # Check if already marked
        if is_attendance_marked_today(student_id):
            return {"success": False, "already_marked": True}
        
        # Load or create attendance file
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            df['student_id'] = df['student_id'].astype(str)
        else:
            df = pd.DataFrame(columns=["student_id", "name", "department", "date", "time", "status"])
        
        # Add new attendance record
        new_record = pd.DataFrame([[str(student_id), student_name, department, date, time, status]], 
                                 columns=["student_id", "name", "department", "date", "time", "status"])
        df = pd.concat([df, new_record], ignore_index=True)
        df.to_csv(ATTENDANCE_FILE, index=False)
        
        return {"success": True, "status": status}
    except Exception as e:
        print(f"Error marking attendance: {e}")
        return {"success": False, "message": str(e)}

# Routes
@app.route('/')
def index():
    # If already logged in, redirect to appropriate dashboard
    if 'is_admin' in session and session['is_admin']:
        return redirect('/admin')
    elif 'student_id' in session:
        return redirect('/dashboard')
    # Show landing page with both login options
    return send_from_directory('templates', 'index.html')

@app.route('/login')
def login_page():
    return send_from_directory('templates', 'login.html')

@app.route('/register')
def register_page():
    return send_from_directory('templates', 'register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    if 'is_admin' in session and session['is_admin']:
        return redirect('/admin')
    return send_from_directory('templates', 'dashboard.html')

@app.route('/admin-login')
def admin_login_page():
    return send_from_directory('templates', 'admin_login.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    return send_from_directory('templates', 'admin.html')

# API: Admin login
@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    try:
        data = request.json
        password = data.get('password')
        
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_name'] = 'Administrator'
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid password"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# API: Register student
@app.route('/api/register-student', methods=['POST'])
def register_student():
    try:
        data = request.json
        student_id = data.get('student_id')
        name = data.get('name')
        department = data.get('department')
        semester = data.get('semester')
        face_descriptor = data.get('face_descriptor')

        if not all([student_id, name, department, semester, face_descriptor]):
            return jsonify({"success": False, "message": "All fields are required"})

        # Load students database
        df = load_students_db()

        # Check if student already exists
        # Ensure student_id is compared as string
        df['student_id'] = df['student_id'].astype(str)
        if str(student_id) in df['student_id'].values:
            # Update existing student
            df.loc[df['student_id'] == str(student_id), 'name'] = name
            df.loc[df['student_id'] == str(student_id), 'department'] = department
            df.loc[df['student_id'] == str(student_id), 'semester'] = semester
            df.loc[df['student_id'] == str(student_id), 'face_descriptor'] = json.dumps(face_descriptor)
        else:
            # Add new student
            new_student = pd.DataFrame([[str(student_id), name, department, semester, json.dumps(face_descriptor)]],
                                      columns=["student_id", "name", "department", "semester", "face_descriptor"])
            df = pd.concat([df, new_student], ignore_index=True)

        # Save to CSV
        df.to_csv(STUDENTS_FILE, index=False)

        # Create session automatically after registration
        session['student_id'] = student_id
        session['student_name'] = name
        session['department'] = department
        session['semester'] = semester

        return jsonify({"success": True, "message": "Student registered successfully"})

    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({"success": False, "message": str(e)})

# API: Face login
@app.route('/api/face-login', methods=['POST'])
def face_login():
    try:
        data = request.json
        face_descriptor = data.get('descriptor', [])
        
        if not face_descriptor:
            return jsonify({"success": False, "message": "No face data provided"})
        
        # Load students database
        students_df = load_students_db()
        
        if students_df.empty:
            return jsonify({"success": False, "message": "No registered students found"})
        
        # Compare with stored descriptors
        best_match = None
        min_distance = float('inf')
        
        # Ensure student_id is loaded as string
        students_df['student_id'] = students_df['student_id'].astype(str)
        
        for idx, row in students_df.iterrows():
            if pd.notna(row['face_descriptor']) and row['face_descriptor']:
                try:
                    stored_descriptor = json.loads(row['face_descriptor'])
                    # Calculate Euclidean distance
                    distance = np.linalg.norm(np.array(face_descriptor) - np.array(stored_descriptor))
                    
                    if distance < min_distance:
                        min_distance = distance
                        best_match = row
                except Exception as e:
                    print(f"Error processing descriptor for {row.get('student_id', 'unknown')}: {e}")
                    continue
        
        # Check if match is good enough
        if best_match is not None and min_distance < MIN_FACE_CONFIDENCE:
            student_id = best_match['student_id']
            student_name = best_match['name']
            department = best_match['department']
            
            # Mark attendance
            attendance_marked = mark_student_attendance(student_id, student_name, department)
            
            # Get existing attendance time if already marked
            existing_time = None
            if not attendance_marked and os.path.exists(ATTENDANCE_FILE):
                df = pd.read_csv(ATTENDANCE_FILE)
                df['student_id'] = df['student_id'].astype(str)
                today = datetime.now().strftime("%Y-%m-%d")
                today_record = df[(df['student_id'] == str(student_id)) & (df['date'] == today)]
                if not today_record.empty:
                    existing_time = today_record.iloc[0]['time']
            
            # Create session
            session['student_id'] = student_id
            session['student_name'] = student_name
            session['department'] = department
            session['semester'] = best_match['semester']
            session['attendance_just_marked'] = attendance_marked
            
            return jsonify({
                "success": True,
                "student_name": student_name,
                "student_id": student_id,
                "attendance_marked": attendance_marked,
                "existing_time": existing_time,
                "confidence": float(1 - min_distance)
            })
        else:
            return jsonify({
                "success": False,
                "message": "Face not recognized. Please ensure you are registered in the system."
            })
            
    except Exception as e:
        print(f"Face login error: {e}")
        return jsonify({"success": False, "message": f"Login error: {str(e)}"})

# API: Get student data
@app.route('/api/student-data')
@login_required
def get_student_data():
    try:
        if 'student_id' not in session:
            return jsonify({"success": False, "message": "Not authenticated"})
        
        student_id = str(session['student_id'])  # Convert to string to match CSV
        print(f"DEBUG: Session student_id = '{student_id}' (type: {type(student_id)})")
        
        # Get attendance records for this student
        attendance_records = []
        total_days = 0
        present_days = 0
        marked_today = False
        
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            print(f"DEBUG: Total rows in CSV: {len(df)}")
            print(f"DEBUG: Unique student IDs in CSV: {df['student_id'].unique()}")
            
            # Convert student_id column to string for comparison
            df['student_id'] = df['student_id'].astype(str)
            print(f"DEBUG: After conversion, unique IDs: {df['student_id'].unique()}")
            
            student_records = df[df['student_id'] == student_id]
            print(f"DEBUG: Found {len(student_records)} records for student_id '{student_id}'")
            
            if len(student_records) > 0:
                print(f"DEBUG: Sample record: {student_records.iloc[0].to_dict()}")
            
            total_days = len(student_records)
            present_days = len(student_records[student_records['status'] == 'Present'])
            
            # Check if marked today
            today = datetime.now().strftime("%Y-%m-%d")
            marked_today = len(student_records[student_records['date'] == today]) > 0
            
            # Get recent records
            attendance_records = student_records.tail(10).to_dict('records')
            # Reverse to show most recent first
            attendance_records.reverse()
            
            # Debug logging
            print(f"DEBUG: Found {len(attendance_records)} records for student {student_id}")
            print(f"DEBUG: Records: {attendance_records}")
        
        response_data = {
            "success": True,
            "student": {
                "student_id": session.get('student_id'),
                "name": session.get('student_name'),
                "department": session.get('department'),
                "semester": session.get('semester')
            },
            "stats": {
                "total_days": total_days,
                "present_days": present_days,
                "marked_today": marked_today
            },
            "attendance_records": attendance_records,
            "attendance_just_marked": session.pop('attendance_just_marked', False)
        }
        
        print(f"DEBUG: Sending response with {len(attendance_records)} records")
        return jsonify(response_data)
    except Exception as e:
        print(f"Error getting student data: {e}")
        return jsonify({"success": False, "message": str(e)})

# API: Get all students (admin only)
@app.route('/api/admin/students')
@admin_required
def get_all_students():
    try:
        students_df = load_students_db()
        
        if students_df.empty:
            return jsonify({"success": True, "students": []})
        
        # Get attendance stats for each student
        students_list = []
        
        if os.path.exists(ATTENDANCE_FILE):
            attendance_df = pd.read_csv(ATTENDANCE_FILE)
            attendance_df['student_id'] = attendance_df['student_id'].astype(str)
            students_df['student_id'] = students_df['student_id'].astype(str)
            
            for idx, student in students_df.iterrows():
                student_id = str(student['student_id'])
                student_records = attendance_df[attendance_df['student_id'] == student_id]
                
                total_days = len(student_records)
                present_days = len(student_records[student_records['status'] == 'Present'])
                percentage = round((present_days / total_days * 100) if total_days > 0 else 0, 1)
                
                students_list.append({
                    "student_id": student_id,
                    "name": student['name'],
                    "department": student['department'],
                    "semester": student['semester'],
                    "total_days": total_days,
                    "present_days": present_days,
                    "percentage": percentage
                })
        else:
            # No attendance records yet
            for idx, student in students_df.iterrows():
                students_list.append({
                    "student_id": student['student_id'],
                    "name": student['name'],
                    "department": student['department'],
                    "semester": student['semester'],
                    "total_days": 0,
                    "present_days": 0,
                    "percentage": 0
                })
        
        return jsonify({"success": True, "students": students_list})
    except Exception as e:
        print(f"Error getting students: {e}")
        return jsonify({"success": False, "message": str(e)})

# API: Get student details (admin)
@app.route('/api/admin/student/<student_id>')
@admin_required
def get_student_details(student_id):
    try:
        students_df = load_students_db()
        students_df['student_id'] = students_df['student_id'].astype(str)
        student = students_df[students_df['student_id'] == str(student_id)]
        
        if student.empty:
            return jsonify({"success": False, "message": "Student not found"})
        
        student_data = student.iloc[0]
        
        # Get attendance records
        attendance_records = []
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            df['student_id'] = df['student_id'].astype(str)
            student_records = df[df['student_id'] == str(student_id)]
            attendance_records = student_records.to_dict('records')
            attendance_records.reverse()
        
        return jsonify({
            "success": True,
            "student": {
                "student_id": student_data['student_id'],
                "name": student_data['name'],
                "department": student_data['department'],
                "semester": student_data['semester']
            },
            "attendance": attendance_records
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# API: Export attendance as CSV
@app.route('/api/export-attendance')
@login_required
def export_attendance():
    try:
        student_id = session.get('student_id')
        
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            df['student_id'] = df['student_id'].astype(str)
            student_records = df[df['student_id'] == str(student_id)]
            
            # Create CSV response
            csv_data = student_records.to_csv(index=False)
            
            from flask import Response
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-disposition": f"attachment; filename=attendance_{student_id}.csv"}
            )
        else:
            return jsonify({"success": False, "message": "No attendance records found"})
    except Exception as e:
        print(f"Export error: {e}")
        return jsonify({"success": False, "message": str(e)})

# API: Export all attendance (admin)
@app.route('/api/admin/export-all')
@admin_required
def export_all_attendance():
    try:
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            csv_data = df.to_csv(index=False)
            
            from flask import Response
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-disposition": "attachment; filename=all_attendance.csv"}
            )
        else:
            return jsonify({"success": False, "message": "No attendance records found"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# API: Delete student (admin only)
@app.route('/api/admin/delete-student/<student_id>', methods=['DELETE'])
@admin_required
def delete_student(student_id):
    try:
        # Load students database
        students_df = load_students_db()
        
        # Check if student exists
        students_df['student_id'] = students_df['student_id'].astype(str)
        if str(student_id) not in students_df['student_id'].values:
            return jsonify({"success": False, "message": "Student not found"})
        
        # Remove student from database
        students_df = students_df[students_df['student_id'] != str(student_id)]
        students_df.to_csv(STUDENTS_FILE, index=False)
        
        # Remove student's attendance records (optional - you can keep them for history)
        if os.path.exists(ATTENDANCE_FILE):
            attendance_df = pd.read_csv(ATTENDANCE_FILE)
            attendance_df['student_id'] = attendance_df['student_id'].astype(str)
            attendance_df = attendance_df[attendance_df['student_id'] != str(student_id)]
            attendance_df.to_csv(ATTENDANCE_FILE, index=False)
        
        return jsonify({"success": True, "message": "Student deleted successfully"})
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({"success": False, "message": str(e)})

# API: Logout
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

# Serve models directory
@app.route('/models/<path:filename>')
def serve_models(filename):
    return send_from_directory('models', filename)

if __name__ == '__main__':
    init_students_file()
    init_attendance_file()
    print("Starting Face Recognition Attendance System...")
    print("Access the application at: http://localhost:5000")
    print(f"Admin login: http://localhost:5000/admin-login (password: {ADMIN_PASSWORD})")
    app.run(debug=True, host='0.0.0.0', port=5000)
