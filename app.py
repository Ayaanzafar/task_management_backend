from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
CORS(app)

# Connect to MySQL database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="task_db"
)

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    user_id = str(uuid.uuid4())
    username = data.get('username')
    password = data.get('password')
    role = data.get('role')

    if not username or not password or not role:
        return jsonify({'error': 'Missing username, password or role'}), 400

    try:
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            return jsonify({'error': 'Username already exists'}), 400

        hashed_password = generate_password_hash(password)
        cursor.execute("INSERT INTO users (user_id, username, password, role) VALUES (%s, %s, %s, %s)",
                       (user_id, username, hashed_password, role))
        db.commit()
        return jsonify({'message': 'User registered successfully'}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Missing username or password'}), 400

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        db_password = user['password']
        if db_password == password or check_password_hash(db_password, password):
            return jsonify({'message': 'Login successful', 'user': user}), 200
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/assign_task', methods=['POST'])
def assign_task():
    data = request.get_json()
    required_fields = ['assigned_by', 'assigned_to', 'title', 'description', 'deadline', 'priority', 'status']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing field: {field}'}), 400

    try:
        deadline = datetime.strptime(data['deadline'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid deadline format. Use YYYY-MM-DD'}), 400

    task_id = str(uuid.uuid4())
    notification_id = str(uuid.uuid4())

    try:
        cursor = db.cursor()

        # 🔐 Validate assigned_by
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (data['assigned_by'],))
        assigned_by_user = cursor.fetchone()
        if not assigned_by_user:
            return jsonify({'error': 'Assigned by user does not exist'}), 400

        # 🔐 Validate assigned_to
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (data['assigned_to'],))
        assigned_to_user = cursor.fetchone()
        if not assigned_to_user:
            return jsonify({'error': 'Assigned to user does not exist'}), 400

        # Proceed with task insert using validated IDs
        assigned_by_id = assigned_by_user[0]
        assigned_to_id = assigned_to_user[0]

        cursor.execute('''INSERT INTO tasks (task_id, assigned_by, assigned_to, title, description, deadline, priority, status)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s)''',
                       (task_id, assigned_by_id, assigned_to_id, data['title'], data['description'],
                        deadline, data['priority'], data['status']))

        message = f'You have been assigned a new task: {data["title"]}'
        cursor.execute('''INSERT INTO notifications (notification_id, user_id, message, is_read)
                          VALUES (%s, %s, %s, %s)''',
                       (notification_id, assigned_to_id, message, False))

        db.commit()
        return jsonify({'message': 'Task assigned and notification sent successfully'}), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500


# @app.route('/get_tasks/<username>', methods=['GET'])
# def get_tasks(username):
#     cursor = db.cursor(dictionary=True)

#     # Check if user exists
#     cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
#     user = cursor.fetchone()
#     if not user:
#         return jsonify({'error': 'User does not exist'}), 404

#     # Fetch tasks assigned to or by the user
#     cursor.execute("SELECT * FROM tasks WHERE assigned_to = %s OR assigned_by = %s", (username, username))
#     tasks = cursor.fetchall()

#     task_list = []
#     for task in tasks:
#         task_dict = {
#             'task_id': task['task_id'],
#             'title': task['title'],
#             'description': task['description'],
#             'assigned_by': task['assigned_by'],
#             'assigned_to': task['assigned_to'],
#             'deadline': task['deadline'].strftime('%Y-%m-%d') if task['deadline'] else None,
#             'priority': task['priority'],
#             'status': task['status']
#         }
#         task_list.append(task_dict)

#     return jsonify(task_list), 200

# @app.route('/get_tasks/<username>', methods=['GET'])
# def get_tasks(username):
#     cursor = db.cursor(dictionary=True)

#     # Debug print to confirm incoming username
#     print(f"Fetching tasks for username: {username}")

#     # Query to check if user exists
#     cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
#     user = cursor.fetchone()

#     # Debug print to confirm what the database returned
#     print(f"User query result: {user}")

#     if not user:
#         return jsonify({'error': 'User does not exist'}), 404

#     user_id = user['user_id']

#     # Fetch tasks for the user
#     cursor.execute("SELECT * FROM tasks WHERE assigned_to = %s", (user_id,))
#     tasks = cursor.fetchall()
#     return jsonify(tasks), 200
@app.route('/get_tasks/by_username/<username>', methods=['GET'])
def get_tasks_by_username(username):
    cursor = db.cursor(dictionary=True)

    print(f"Fetching tasks for username: {username}")
    cursor.execute("SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s)", (username,))
    user = cursor.fetchone()

    print(f"User query result: {user}")

    if not user:
        return jsonify({'error': 'User does not exist'}), 404

    user_id = user['user_id']
    cursor.execute("SELECT * FROM tasks WHERE assigned_to = %s", (user_id,))
    tasks = cursor.fetchall()
    return jsonify(tasks), 200



@app.route('/notifications', methods=['POST'])
def get_notifications():
    data = request.get_json()
    user_id = data.get('user_id')

    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM notifications WHERE user_id = %s", (user_id,))
        notifications = cursor.fetchall()
        return jsonify(notifications), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/mark_read', methods=['POST'])
def mark_notifications_read():
    data = request.get_json()
    user_id = data.get('user_id')

    try:
        cursor = db.cursor()
        cursor.execute("UPDATE notifications SET is_read = %s WHERE user_id = %s", (True, user_id))
        db.commit()
        return jsonify({'message': 'Notifications marked as read'}), 200
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT user_id, username, role FROM users")
        users = cursor.fetchall()
        return jsonify(users), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ✅ GET ROUTE TO FETCH TASKS BY USER ID (minor bugfix: corrected 'username' to 'user_id')
@app.route('/get_tasks/<user_id>', methods=['GET'])
def get_tasks_by_user(user_id):
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("SELECT * FROM tasks WHERE assigned_to = %s", (user_id,))
        tasks = cursor.fetchall()
        return jsonify(tasks), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
