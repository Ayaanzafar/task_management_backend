from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ---------------- DATABASE CONNECTION ----------------
conn = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='task_db'
)
cursor = conn.cursor()

# ---------------- ROOT ----------------
@app.route('/')
def home():
    return 'Flask API is running!'

# ---------------- SIGNUP ----------------
@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        required_fields = ['username', 'email', 'phone', 'password', 'role']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        cursor.execute("SELECT * FROM users WHERE username = %s", (data['username'],))
        if cursor.fetchone():
            return jsonify({'message': 'User already exists'}), 409

        user_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO users (user_id, username, email, phone, password, role, fcm_token)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id, data['username'], data['email'], data['phone'],
            data['password'], data['role'], data.get('fcm_token', '')
        ))
        conn.commit()
        return jsonify({'message': 'Signup successful'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- LOGIN ----------------
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s",
                       (data['username'], data['password']))
        user = cursor.fetchone()
        if user:
            return jsonify({
                'message': 'Login successful',
                'user_id': user[0],
                'username': user[1],
                'role': user[5]
            }), 200
        return jsonify({'message': 'Invalid username or password'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- ASSIGN TASK ----------------
@app.route('/assign_task', methods=['POST'])
def assign_task():
    try:
        data = request.get_json()
        required_fields = ['assigned_by', 'assigned_to', 'title']
        if not all(field in data for field in required_fields):
            return jsonify({'message': 'Missing required fields'}), 400

        # Get user IDs
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (data['assigned_by'],))
        assigner = cursor.fetchone()
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (data['assigned_to'],))
        assignee = cursor.fetchone()

        if not assigner or not assignee:
            return jsonify({'message': 'Assigner or assignee not found'}), 404

        task_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO tasks (task_id, title, description, assigned_to, assigned_by, status, due_date, progress)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            task_id, data['title'], data.get('description', ''), assignee[0], assigner[0],
            data.get('status', 'Pending'), data.get('due_date', datetime.now().strftime('%Y-%m-%d')),
            data.get('progress', '0%')
        ))
        conn.commit()

        # Add notification
        notification_id = str(uuid.uuid4())
        message = f"You have a new task: {data['title']}"
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("""
            INSERT INTO notifications (notification_id, user_id, message, is_read, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (notification_id, assignee[0], message, False, created_at))
        conn.commit()

        return jsonify({'message': 'Task assigned and notification sent'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- GET NOTIFICATIONS ----------------
@app.route('/notifications/<username>', methods=['GET'])
def get_notifications(username):
    try:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'message': 'User not found'}), 404

        cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user[0],))
        notifications = cursor.fetchall()

        return jsonify([
            {
                'notification_id': n[0],
                'user_id': n[1],
                'message': n[2],
                'is_read': n[3],
                'created_at': n[4].strftime('%Y-%m-%d %H:%M:%S') if n[4] else None
            } for n in notifications
        ]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ---------------- MARK AS READ ----------------
@app.route('/notifications/mark_read/<notification_id>', methods=['PUT'])
def mark_read(notification_id):
    try:
        cursor.execute("UPDATE notifications SET is_read = TRUE WHERE notification_id = %s", (notification_id,))
        conn.commit()
        return jsonify({'message': 'Notification marked as read'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/create_task', methods=['POST'])
def create_task():
    data = request.get_json()
    task_id = str(uuid.uuid4())
    title = data['title']
    description = data['description']
    assigned_by = data['assigned_by']
    assigned_to = data['assigned_to']
    deadline = data['deadline']
    priority = data['priority']

    cursor.execute("INSERT INTO tasks (task_id, title, description, assigned_by, assigned_to, deadline, priority) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                   (task_id, title, description, assigned_by, assigned_to, deadline, priority))
    conn.commit()

    return jsonify({'message': 'Task created successfully'}), 200

@app.route('/users', methods=['GET'])
def get_users():
    cursor.execute("SELECT username FROM users")
    users = [row[0] for row in cursor.fetchall()]
    return jsonify(users), 200


# ✅ Get all tasks
# @app.route('/tasks', methods=['GET'])
# def get_tasks():
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)
#         cursor.execute("SELECT * FROM tasks ORDER BY deadline ASC")
#         tasks = cursor.fetchall()
#         for task in tasks:
#             if isinstance(task['deadline'], (bytes, bytearray)):
#                 task['deadline'] = task['deadline'].decode()  # just in case
#         return jsonify(tasks)
#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
#     finally:
#         cursor.close()
#         conn.close()

@app.route('/tasks/<username>', methods=['GET'])
def get_tasks(username):
    try:
        # Get user_id and role
        cursor.execute("SELECT user_id, role FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'message': 'User not found'}), 404
        user_id, role = user

        if role in ['Admin', 'Super Admin', 'Team Leader']:
            cursor.execute("SELECT * FROM tasks ORDER BY due_date")
        else:
            cursor.execute("SELECT * FROM tasks WHERE assigned_to = %s ORDER BY due_date", (user_id,))

        tasks = cursor.fetchall()
        return jsonify([
            {
                'task_id': t[0],
                'title': t[1],
                'description': t[2],
                'assigned_to': t[3],
                'assigned_by': t[4],
                'status': t[5],
                'due_date': t[6].strftime('%Y-%m-%d') if t[6] else None,
                'progress': t[7]
            } for t in tasks
        ]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ✅ Update FCM token
@app.route('/update_fcm_token', methods=['POST'])
def update_fcm_token():
    data = request.get_json()
    username = data.get('username')
    fcm_token = data.get('fcm_token')

    if not username or not fcm_token:
        return jsonify({'error': 'Missing username or token'}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET fcm_token = %s WHERE username = %s", (fcm_token, username))
        conn.commit()
        return jsonify({'message': 'FCM token updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

# ---------------- MAIN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)