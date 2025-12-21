from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
import cv2
import numpy as np
import face_recognition
import pandas as pd
import os
import base64
from datetime import datetime
import json
import threading
import time

app = Flask(__name__)
CORS(app)

# Configuration
KNOWN_FACES_DIR = "known_faces"
ATTENDANCE_FILE = "attendance.csv"

# Global variables
known_face_encodings = []
known_face_names = []
entry_logged = {}
attendance_log = []

# Load known faces
def load_known_faces():
    global known_face_encodings, known_face_names
    known_face_encodings = []
    known_face_names = []
    
    if not os.path.exists(KNOWN_FACES_DIR):
        os.makedirs(KNOWN_FACES_DIR)
        print(f"Created {KNOWN_FACES_DIR} directory. Please add face images there.")
        return
    
    for file in os.listdir(KNOWN_FACES_DIR):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            try:
                image_path = os.path.join(KNOWN_FACES_DIR, file)
                image = face_recognition.load_image_file(image_path)
                encodings = face_recognition.face_encodings(image)
                if encodings:
                    known_face_encodings.append(encodings[0])
                    known_face_names.append(os.path.splitext(file)[0])
                    print(f"Loaded face: {os.path.splitext(file)[0]}")
            except Exception as e:
                print(f"Error loading {file}: {e}")

# Initialize attendance log
def init_attendance_file():
    if not os.path.exists(ATTENDANCE_FILE):
        df = pd.DataFrame(columns=["Name", "Status", "Time", "Duration"])
        df.to_csv(ATTENDANCE_FILE, index=False)

# Function to mark attendance
def mark_attendance(name, status, duration=None):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df = pd.read_csv(ATTENDANCE_FILE)
    
    new_entry = pd.DataFrame([[name, status, now, duration]], columns=["Name", "Status", "Time", "Duration"])
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(ATTENDANCE_FILE, index=False)
    
    # Add to in-memory log
    attendance_log.append({
        "name": name,
        "status": status,
        "time": now,
        "duration": duration
    })
    
    print(f"{status} recorded for {name} at {now} (Duration: {duration if duration else 'N/A'})")

# Process frame for face recognition
def process_frame(frame_data):
    try:
        # Decode base64 image
        image_data = base64.b64decode(frame_data.split(',')[1])
        nparr = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return {"faces": [], "error": "Failed to decode image"}
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize for faster processing
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
        
        # Detect faces
        face_locations = face_recognition.face_locations(small_frame)
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)
        
        detected_faces = []
        current_name = None
        
        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            name = "Unknown"
            color = "red"
            confidence = 0
            
            if len(known_face_encodings) > 0:
                # Compare faces
                matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else None
                
                if best_match_index is not None and matches[best_match_index]:
                    name = known_face_names[best_match_index]
                    color = "green"
                    confidence = 1 - face_distances[best_match_index]
                    current_name = name
                    
                    # Handle attendance logging
                    now = datetime.now()
                    
                    # Log entry if person is detected for the first time
                    if name not in entry_logged:
                        entry_logged[name] = now
                        mark_attendance(name, "Entry")
                    
                    # Log exit if previously marked as entry and at least 60 seconds have passed
                    elif name in entry_logged and (now - entry_logged[name]).seconds > 60:
                        duration = (now - entry_logged[name]).seconds
                        mark_attendance(name, "Exit", f"{duration} seconds")
                        del entry_logged[name]
            
            # Scale back face locations
            top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
            
            # Calculate accuracy percentage (confidence as percentage)
            accuracy_percentage = confidence * 100 if confidence > 0 else 0
            
            detected_faces.append({
                "name": name,
                "color": color,
                "box": {
                    "top": int(top),
                    "right": int(right),
                    "bottom": int(bottom),
                    "left": int(left)
                },
                "confidence": float(confidence),
                "accuracy": round(accuracy_percentage, 1)
            })
        
        return {
            "faces": detected_faces,
            "current_person": current_name if current_name else None,
            "active_count": len(entry_logged)
        }
        
    except Exception as e:
        return {"faces": [], "error": str(e)}

# Routes
@app.route('/')
def index():
    return render_template('face_recognition_web.html')

@app.route('/api/recognize', methods=['POST'])
def recognize():
    try:
        data = request.json
        frame_data = data.get('frame', '')
        
        if not frame_data:
            return jsonify({"error": "No frame data provided"}), 400
        
        result = process_frame(frame_data)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    try:
        # Load from CSV file
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            
            # Handle empty CSV or empty dataframe
            if df.empty:
                return jsonify({"attendance": []})
            
            # Convert to our format, handling NaN values
            attendance = []
            for _, row in df.iterrows():
                # Handle NaN values by converting to None
                name = str(row["Name"]) if pd.notna(row["Name"]) else "Unknown"
                status = str(row["Status"]) if pd.notna(row["Status"]) else "Unknown"
                time = str(row["Time"]) if pd.notna(row["Time"]) else ""
                
                # Handle Duration - can be NaN, empty string, or valid value
                duration = None
                if "Duration" in row and pd.notna(row["Duration"]):
                    duration_str = str(row["Duration"]).strip()
                    if duration_str and duration_str.lower() != "nan" and duration_str != "":
                        duration = duration_str
                
                attendance.append({
                    "name": name,
                    "status": status,
                    "time": time,
                    "duration": duration
                })
            
            print(f"Loaded {len(attendance)} attendance records from {ATTENDANCE_FILE}")
            return jsonify({"attendance": attendance})
        else:
            print(f"Attendance file {ATTENDANCE_FILE} not found")
            return jsonify({"attendance": []})
    except Exception as e:
        print(f"Error reading attendance CSV: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.read_csv(ATTENDANCE_FILE)
            entries = len(df[df["Status"] == "Entry"])
            exits = len(df[df["Status"] == "Exit"])
        else:
            entries = 0
            exits = 0
        
        return jsonify({
            "total_entries": entries,
            "total_exits": exits,
            "active_now": len(entry_logged)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_attendance():
    try:
        global entry_logged, attendance_log
        entry_logged = {}
        attendance_log = []
        
        if os.path.exists(ATTENDANCE_FILE):
            df = pd.DataFrame(columns=["Name", "Status", "Time", "Duration"])
            df.to_csv(ATTENDANCE_FILE, index=False)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Loading known faces...")
    load_known_faces()
    print(f"Loaded {len(known_face_names)} known faces")
    
    print("Initializing attendance file...")
    init_attendance_file()
    
    print("Starting Flask server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)

