import cv2
import numpy as np
import face_recognition
import pandas as pd
import os
from datetime import datetime, timedelta

# Load known faces and names
KNOWN_FACES_DIR = "known_faces"
ATTENDANCE_FILE = "attendance.csv"

known_face_encodings = []
known_face_names = []
entry_logged = {}  # Active entries
exit_logged = {}   # Last exit times
waiting_shown = {} # Tracks if waiting message has been shown

# Load known faces
for file in os.listdir(KNOWN_FACES_DIR):
    image = face_recognition.load_image_file(f"{KNOWN_FACES_DIR}/{file}")
    encodings = face_recognition.face_encodings(image)
    if encodings:
        known_face_encodings.append(encodings[0])
        known_face_names.append(os.path.splitext(file)[0])  # Extract name from file

# Initialize attendance log
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
    print(f"{status} recorded for {name} at {now} (Duration: {duration if duration else 'N/A'})")

# Load previous entry and exit times
def load_previous_entries():
    df = pd.read_csv(ATTENDANCE_FILE)
    for _, row in df.iterrows():
        time_logged = datetime.strptime(row["Time"], "%Y-%m-%d %H:%M:%S")
        if row["Status"] == "Entry":
            entry_logged[row["Name"]] = time_logged
        elif row["Status"] == "Exit":
            exit_logged[row["Name"]] = time_logged

# Prevent false exits on startup
def clean_false_exits():
    for name in list(entry_logged.keys()):
        if name in exit_logged and exit_logged[name] > entry_logged[name]:
            del entry_logged[name]  # Remove false entry

load_previous_entries()
clean_false_exits()  # Fix false exits

# Initialize webcam
video_capture = cv2.VideoCapture(0)

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # Resize frame for faster processing
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Detect faces
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

    now = datetime.now()

    for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        name = "Unknown"
        color = (0, 0, 255)  # Red for unknown faces

        # Find best match
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
        best_match_index = np.argmin(face_distances) if len(face_distances) > 0 else None

        if best_match_index is not None and matches[best_match_index]:
            name = known_face_names[best_match_index]
            color = (0, 255, 0)  # Green for recognized faces

            # Check exit time before re-entry
            if name in exit_logged:
                time_since_exit = (now - exit_logged[name]).seconds
                if time_since_exit < 30:
                    if name not in waiting_shown:  # Show message only once
                        print(f"⏳ Waiting 30 seconds before allowing re-entry for {name}...")
                        waiting_shown[name] = True
                    continue  # Skip new entry for now
                else:
                    del exit_logged[name]  # Allow re-entry
                    waiting_shown.pop(name, None)  # Reset waiting flag

            # Log entry if not already inside
            if name not in entry_logged:
                entry_logged[name] = now
                mark_attendance(name, "Entry")

            # Log exit only if person had an entry
            elif name in entry_logged:
                time_inside = (now - entry_logged[name]).seconds
                if time_inside >= 60:
                    mark_attendance(name, "Exit", f"{time_inside} seconds")
                    exit_logged[name] = now
                    del entry_logged[name]  # Remove from active log

        # Scale face locations back to original size
        top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4

        # Draw rectangle and label
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

    # Display frame
    cv2.imshow("Real-Time Face Recognition", frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

# Release resources
video_capture.release()
cv2.destroyAllWindows()
