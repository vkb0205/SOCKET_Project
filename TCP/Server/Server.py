# echo-server.py

from re import I
import socket
import threading
import sys
# Sử dụng 1 file Text hoặc JSON (hoặc sử dụng file có cấu trúc khác) để lưu danh sách các file cho phép client download gồm tên file, và dung lượng. Ví dụ file text (.txt):

#File1.zip 5MB
#File2.zip 10MB
#File3.zip 20MB
#File4.zip 50MB
#File5.zip 100MB
#File6.zip 200MB
#File7.zip 512MB
#File8.zip 1GB

#Server sẽ nhận yêu cầu từ Client download file nào, từ offset nào để gửi đến Client.
#File chứa trên Server, không được cắt nhỏ sẵn thành các file nhỏ hơn.
#Server có thể phục vụ đồng thời  yêu cầu download file từ nhiều client.

# Load the list of files and their sizes from a text file
# Load the list of files and their sizes from a text file
def load_file_list(file_path):
    file_list = {}
    with open(file_path, 'r') as f:
        for line in f:
            name, size = line.strip().split()
            file_list[name] = size
    return file_list



# Handle client requests
def handle_client(conn, addr, file_list):
    print(f"\nConnected by {addr}")
    flag = True
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            # Parse the request
            request = data.split()
            command = request[0]

            if command == 'LIST':
                # Send the list of files and their sizes
                if flag:
                    print(f"Sending file list to {addr}")
                    flag = False
                file_list = load_file_list("input.txt")
                file_list_str = '\n'.join([f"{name} {size}" for name, size in file_list.items()])
                conn.sendall(file_list_str.encode() + b'\n')
            else:
                flag = True
                if command == 'DOWNLOAD' and len(request) == 5:
                    print(f"Downloading {request[1]} from {addr}")
                    filename, chunk_id, start, end = request[1], int(request[2]), int(request[3]), int(request[4])
                    if filename not in file_list:
                        conn.sendall(b'File not found\n')
                        continue
                    # Send the requested file chunk
                    try:
                        with open(filename, 'rb') as f:
                            f.seek(start)
                            bytes_to_send = end - start + 1
                            while bytes_to_send > 0:
                                chunk = f.read(min(1024, bytes_to_send))
                                if not chunk:
                                    break
                                conn.sendall(chunk)
                                bytes_to_send -= len(chunk)
                    except Exception as e:
                        conn.sendall(b'Error reading file\n')
                elif command == 'DOWNLOADING':
                    print(f"Downloading in progress")
                    # Handle DOWNLOADING protocol
                    conn.sendall(b'Downloading in progress\n')
                elif command == 'QUIT':
                    print(f"Connection closed\n")
                    # Handle END protocol
                    conn.sendall(b'Connection closed\n')
                    break
                else:
                    conn.sendall(b'Invalid request\n')

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()


        
        


def main():
    HOST = "0.0.0.0"
    PORT = 9000
    FILE_LIST_PATH = "input.txt"

    file_list = load_file_list(FILE_LIST_PATH)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s: #Socket that the server use to accept new connections 
        s.bind((HOST, PORT))
        s.listen(1)
        print(f"Server listening on {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_client, args=(conn, addr, file_list)).start()

if __name__ == "__main__":
    main()