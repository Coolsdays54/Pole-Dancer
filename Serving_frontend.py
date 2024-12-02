from flask import Flask, jsonify
import pymysql
from pymysql import OperationalError
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MySQL Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'Sensor_user'),
    'password': os.getenv('DB_PASSWORD', 'StrongPassword'),
    'database': os.getenv('DB_NAME', 'sensor_data_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

app = Flask(__name__)

def get_db_connection():
    """
    Establishes a new database connection.
    Returns:
        connection: A pymysql connection object.
    """
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except OperationalError as e:
        print(f"Could not connect to the database: {e}")
        return None

@app.route('/api/sensor_data', methods=['GET'])
def get_sensor_data():
    """
    Fetches sensor data (ID, lat, longi, pitch, roll, yaw, temperature, and pressure) from the database.
    Returns:
        JSON: Sensor data as a JSON object.
    """
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        with connection.cursor() as cursor:
            # Select all the necessary columns
            cursor.execute("""
                SELECT id, lat, `Longi`, pitch, roll, yaw, Temperature, Pressure 
                FROM sensor_readings
            """)
            results = cursor.fetchall()
            return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if connection:
            connection.close()

@app.route('/')
def index():
    return app.send_static_file('PoleDancer2.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)