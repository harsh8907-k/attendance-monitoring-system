import cv2
import numpy as np
import face_recognition
import pandas as pd
import os
from datetime import datetime

# Load known faces and names
KNOWN_FACES_DIR = "known_faces"
ATTENDANCE_FILE = "attendance.csv"

known_face_encodings = []
known_face_names = []
entry_logged = {}  # Track entry time

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

# Initialize webcam
video_capture = cv2.VideoCapture(0)

while True:
    ret, frame = video_capture.read()
    if not ret:
        break

    # Resize frame to 1/4 size for faster processing
    small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25, interpolation=cv2.INTER_LINEAR)
    rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

    # Detect faces
    face_locations = face_recognition.face_locations(rgb_small_frame)
    face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

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

            now = datetime.now()
            
            # Log entry if person is detected for the first time
            if name not in entry_logged:
                entry_logged[name] = now  # Store entry time
                mark_attendance(name, "Entry")
            
            # Log exit only if previously marked as entry and at least 60 seconds have passed
            elif name in entry_logged and (now - entry_logged[name]).seconds > 60:
                duration = (now - entry_logged[name]).seconds  # Calculate duration
                mark_attendance(name, "Exit", f"{duration} seconds")
                del entry_logged[name]  # Remove entry status after exit

        # Scale back face locations since we resized the frame
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
