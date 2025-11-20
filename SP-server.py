import socket
from threading import Thread
from queue import Queue
from datetime import datetime

BUFFER_SIZE = 1024

class Server(Thread):
    def __init__(self, address: str, port: int):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((address, port))
        self.sock.listen()
        self.msg_queue = Queue()
        self.clients = [] 
        self.start()

    def run(self):
        print("Server started at 127.0.0.1:9002")
        MessageHandler(self.msg_queue, self.clients).start()
        
        while True:
            try:
                client_conn, client_addr = self.sock.accept()
                print(f"Client with address {client_addr} connected!")
                client_handler = ClientHandler(client_conn, self.msg_queue, self.clients)
                self.clients.append(client_handler)
            except Exception as e:
                print(f"Server error: {e}")

class ClientHandler(Thread):
    def __init__(self, conn, msg_queue, clients_list):
        super().__init__(daemon=True)
        self.conn = conn
        self.msg_queue = msg_queue
        self.clients_list = clients_list
        self.name = "Unknown"
        self.ready = False
        self.start()

    def run(self):
        try:
            # sending a name request
            self.conn.send("Please enter your name".encode())
            
            # getting a users name
            name_msg = self.recv()
            self.name = name_msg.strip() if name_msg else "Anonymous"
            
            # greetinds!
            self.conn.send(f"Hello, {self.name}!".encode())
            
            self.ready = True
            
            # main loop
            while True:
                data = self.conn.recv(BUFFER_SIZE)
                if not data:
                    break
                    
                text = data.decode('utf-8').strip()
                if text:
                    print(f"Received from {self.name}: {text}")
                    date = datetime.now().strftime("%H:%M:%S")
                    formatted_text = f"[{date}] {self.name}: {text}"
                    self.msg_queue.put((formatted_text, self))
                    
        except Exception as e:
            print(f"Client {self.name} error: {e}")
        finally:
            # delete a user if he/she disconnects
            if self in self.clients_list:
                self.clients_list.remove(self)
            print(f"Client {self.name} disconnected")

    def send(self, text):
        try:
            self.conn.send(text.encode())
        except:
            pass

    def recv(self):
        try:
            msg = self.conn.recv(BUFFER_SIZE)
            return msg.decode("utf-8")
        except:
            return ""

class MessageHandler(Thread):
    def __init__(self, msg_queue, clients):
        super().__init__(daemon=True)
        self.msg_queue = msg_queue
        self.clients = clients

    def run(self):
        while True:
            try:
                message, sender = self.msg_queue.get()
                print(f"Broadcasting: {message}")
                
                # send send!
                for client in self.clients[:]:
                    if client.is_alive() and client.ready:
                        client.send(message)
            except Exception as e:
                print(f"Message handler error: {e}")

if __name__ == '__main__':
    server = Server("127.0.0.1", 9002)
    try:
        while True:
            input("Press enter to stop the server\n")
            break
    except KeyboardInterrupt:
        print("Server stopped!")