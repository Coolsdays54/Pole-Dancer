import socket
import requests

#Configuration
HOST = '192.168.10.62'
PORT = 65432
WEBHOOK_URL = 'http://localhost:8080/update'

def main():
    #Create a socket object
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        #bind to address and port
        s.bind((HOST, PORT))
        s.listen()
        
        print(f"Listening on {HOST}:{PORT}")
        
        while True:
            #Wait for a connection
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                #Receive data
                data = conn.recv(1024)
                if data:
                    #Convert data to string and send to the web server
                    data_str = data.decode('utf-8')
                    print(f"Received data: {data_str}")
                    
if __name__ == "__main__":
    main()