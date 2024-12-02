import socket
import logging
import threading
import signal
import sys
import pymysql
from pymysql import OperationalError
from dotenv import load_dotenv
import os
import re

# Load environment variables from .env file
load_dotenv()

# Configuration
HOST = '192.168.10.62'  # Server IP address
PORT = 65432            # Port to listen on

# MySQL Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'sensor_user'),
    'password': os.getenv('DB_PASSWORD', 'your_password'),
    'database': os.getenv('DB_NAME', 'sensor_data_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Flag to indicate server should keep running
running = True

def get_db_connection():
    """
    Establishes a new database connection.
    Returns:
        connection: A pymysql connection object.
    """
    try:
        connection = pymysql.connect(**DB_CONFIG)
        logging.info("Connected to the MySQL database.")
        return connection
    except OperationalError as e:
        logging.critical(f"Could not connect to the database: {e}")
        sys.exit(1)

def validate_data(pitch, roll, yaw, timestamp, lat, longi):
    """
    Validates the sensor data.
    
    Args:
        pitch (float): Pitch value.
        roll (float): Roll value.
        yaw (float): Yaw value.
        timestamp (str): Timestamp of the data.
        lat (float): Latitude value.
        longi (float): Longitude value.
    
    Returns:
        bool: True if data is valid, False otherwise.
    """
    # Example validations
    if not (-90 <= pitch <= 90):
        logging.warning(f"Invalid pitch value: {pitch}")
        return False
    if not (-180 <= roll <= 180):
        logging.warning(f"Invalid roll value: {roll}")
        return False
    if not (-180 <= yaw <= 180):
        logging.warning(f"Invalid yaw value: {yaw}")
        return False
    # Additional timestamp format validation can be added here if needed
    return True

def insert_into_db(id_, pitch, roll, yaw, timestamp, lat, longi, temp, pressure):
    """
    Inserts the received sensor data into the MySQL database.

    Args:
        id_ (str): Unique identifier.
        pitch (float): Pitch value.
        roll (float): Roll value.
        yaw (float): Yaw value.
        timestamp (str): Timestamp of the data.
        lat (float): Latitude value.
        longi (float): Longitude value.
        temp (float): Temperature value.
        pressure (float): Pressure value.
    """
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            # Ensure the SQL query matches the correct column names in the database
            insert_query = """
                INSERT INTO sensor_readings (id, pitch, roll, yaw, timestamp, lat, `Longi`, Temperature, Pressure)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    pitch = VALUES(pitch),
                    roll = VALUES(roll),
                    yaw = VALUES(yaw),
                    timestamp = VALUES(timestamp),
                    lat = VALUES(lat),
                    `Longi` = VALUES(`Longi`),
                    Temperature = VALUES(Temperature),
                    Pressure = VALUES(Pressure)
            """
            # Execute the query with the correct number of parameters
            cursor.execute(insert_query, (id_, pitch, roll, yaw, timestamp, lat, longi, temp, pressure))
            connection.commit()
            if cursor.rowcount == 1:
                logging.info(f"Inserted data into database: ID={id_}, Pitch={pitch}, Roll={roll}, Yaw={yaw}, Time={timestamp}, Lat={lat}, Longi={longi}, Temp={temp}, Pressure={pressure}")
            elif cursor.rowcount == 2:
                logging.info(f"Updated existing record in database: ID={id_}, Pitch={pitch}, Roll={roll}, Yaw={yaw}, Time={timestamp}, Lat={lat}, Longi={longi}, Temp={temp}, Pressure={pressure}")
    except pymysql.err.IntegrityError as ie:
        if ie.args[0] == 1062:
            logging.error(f"Duplicate entry for ID {id_}: {ie}")
        else:
            logging.error(f"Integrity error: {ie}")
    except Exception as e:
        logging.error(f"Error inserting/updating data into database: {e}")
    finally:
        if connection:
            connection.close()
            logging.debug("Database connection closed.")

def parse_message(message):
    """
    Parses the incoming message and extracts id, pitch, roll, yaw, timestamp, lat, longi, temp, and pressure.

    Args:
        message (str): The raw message string.

    Returns:
        tuple: (id_, pitch, roll, yaw, timestamp, lat, longi, temp, pressure) if parsing is successful.
        None: If parsing fails.
    """
    try:
        # Updated regular expression to handle missing commas
        pattern = r'(\w+):\s*([^:]+?)(?=\s+\w+:|$)'
        matches = re.findall(pattern, message)
        data_dict = {}
        for key, value in matches:
            key = key.strip().lower()
            value = value.strip().rstrip(',')  # Remove any trailing commas
            data_dict[key] = value
            
        logging.debug(f"Data dictionary after parsing: {data_dict}")  # Added for debugging

        # Extract and convert fields
        id_ = data_dict.get('id')
        pitch = float(data_dict.get('pitch')) if data_dict.get('pitch') else None
        roll = float(data_dict.get('roll')) if data_dict.get('roll') else None
        yaw = float(data_dict.get('yaw')) if data_dict.get('yaw') else None
        timestamp = data_dict.get('time')
        #print (timestamp)
        if timestamp:
            # Insert a space between the date and time parts if it's missing
            timestamp = re.sub(r'(\d{4}-\d{2}-\d{2})-(\d{2}:\d{2}:\d{2})', r'\1 \2', timestamp)
        lat = float(data_dict.get('lat')) if data_dict.get('lat') else None
        longi = float(data_dict.get('longi')) if data_dict.get('longi') else None
        temp = float(data_dict.get('temp')) if data_dict.get('temp') else None
        pressure = float(data_dict.get('pressure')) if data_dict.get('pressure') else None

        # Check for mandatory fields
        if not all([id_, pitch is not None, roll is not None, yaw is not None, timestamp, lat is not None, longi is not None, temp is not None, pressure is not None]):
            logging.error("Missing one or more required fields.")
            logging.debug(f"Parsed data: {data_dict}")  # Added for debugging
            return None

        return id_, pitch, roll, yaw, timestamp, lat, longi, temp, pressure
    except (ValueError, TypeError) as ve:
        logging.error(f"Error parsing message: {ve}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during parsing: {e}")
        return None

def handle_client(conn, addr):
    """
    Handles the client connection: receives data, parses it, and inserts into the database.

    Args:
        conn (socket.socket): The client socket connection.
        addr (tuple): The client's address.
    """
    with conn:
        logging.info(f"Connected by {addr}")
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    logging.info(f"Connection closed by {addr}")
                    break
                # Assuming data is sent as "ID: 004018019000001, Pitch: -2.02, Roll: 0.72, Yaw: -165.59, Time: 2024-10-09 11:56:31, Lat: 39.688137, Long: -77.741971, Temp: 83.98400000000001, Pressure: 987.956298828125"
                data_str = data.decode('utf-8').strip()
                #print(data_str)
                logging.info(f"Received data: {data_str}")

                # Parse the data
                parsed_data = parse_message(data_str)
                if parsed_data:
                    id_, pitch, roll, yaw, timestamp, lat, long_, temp, pressure = parsed_data
                    if validate_data(pitch, roll, yaw, timestamp, lat, long_):
                        insert_into_db(id_, pitch, roll, yaw, timestamp, lat, long_, temp, pressure)
                    else:
                        logging.warning(f"Received invalid data from {addr}: {data_str}")
                else:
                    logging.warning(f"Failed to parse message from {addr}: {data_str}")
        except Exception as e:
            logging.error(f"Error handling client {addr}: {e}")

def signal_handler(sig, frame):
    global running
    logging.info("Shutting down the server...")
    running = False
    sys.exit(0)

def main():
    global running
    # Register the signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, PORT))
            s.listen()
            s.settimeout(1.0)  # Set timeout to allow periodic check of the running flag
            logging.info(f"Server listening on {HOST}:{PORT}")

            while running:
                try:
                    conn, addr = s.accept()
                    client_thread = threading.Thread(target=handle_client, args=(conn, addr))
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue  # Check the running flag again
        except Exception as e:
            logging.critical(f"Server error: {e}")
        finally:
            logging.info("Server has been shut down.")

if __name__ == "__main__":
    main()