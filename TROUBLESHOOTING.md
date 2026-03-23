# Face Recognition Troubleshooting Guide

## Issue: Camera Not Recognizing Face

### Most Common Cause: Not Registered Yet ⚠️

**You MUST register before login works!**

1. Open: `http://localhost:5000/register`
2. Fill in ALL fields (Student ID, Name, Department, Semester)
3. Look directly at camera
4. Click "Register Student"
5. See success message
6. THEN try login page

---

### If Already Registered:

#### Check 1: Verify Registration Data
```bash
# Check if students.csv has your face data
cd d:\attendance-system-using-image
notepad students.csv
```

**Look for:**
- Your student ID in the file
- `face_descriptor` column has a long JSON array (not empty)

#### Check 2: Lighting & Position
- ✅ Face the camera directly
- ✅ Ensure good lighting (not too dark/bright)
- ✅ Remove glasses/hat if worn during registration
- ✅ Same background/position as registration

#### Check 3: Adjust Confidence Threshold

If you're registered but still not recognized, the threshold might be too strict.

Edit `app.py` line 27:
```python
# Change from:
MIN_FACE_CONFIDENCE = 0.5

# To more lenient:
MIN_FACE_CONFIDENCE = 0.6  # or even 0.7
```

Then restart Flask server.

#### Check 4: Browser Console Errors

1. Press F12 in browser
2. Go to Console tab
3. Look for errors
4. Common issues:
   - "No face data provided" → Camera not detecting face
   - "Face not recognized" → Threshold too strict OR not registered
   - "No registered students" → Database empty

#### Check 5: Re-register with Better Conditions

Sometimes the original registration had poor lighting/angle:

1. Go to registration page again
2. Use the SAME student ID
3. Better lighting this time
4. Face directly at camera
5. Register again (it will update your face data)

---

## Quick Debug Commands

### Check Students Database
```bash
cd d:\attendance-system-using-image
python -c "import pandas as pd; df = pd.read_csv('students.csv'); print(df[['student_id', 'name']]); print(f'\nTotal students: {len(df)}')"
```

### Check Attendance Records
```bash
python -c "import pandas as pd; import os; print(pd.read_csv('attendance.csv') if os.path.exists('attendance.csv') else 'No attendance yet')"
```

---

## Step-by-Step Test

1. **Register First** (if not done):
   ```
   URL: http://localhost:5000/register
   Student ID: TEST001
   Name: Test Student
   Department: Computer Science
   Semester: 5
   → Capture face → Submit
   ```

2. **Verify Registration**:
   - Check students.csv has TEST001
   - face_descriptor column should have data

3. **Test Login**:
   ```
   URL: http://localhost:5000/login
   → Position face → Wait for recognition
   ```

4. **Expected Behavior**:
   - Face detected (orange box appears)
   - "Face detected! Verifying identity..." message
   - Then either:
     - ✅ "Login Successful!" → Redirects to dashboard
     - ❌ "Face not recognized" → Check threshold or re-register

---

## Still Not Working?

**Check Flask Server Logs**

Look at the terminal where Flask is running for error messages like:
- "No registered students found"
- "Error loading students database"
- "Face login error: ..."

**Common Fixes:**
- Restart Flask server
- Clear browser cache
- Try different browser
- Re-register with updated face data
