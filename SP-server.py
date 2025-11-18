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
        self.msg_queue: Queue = Queue()
        self.clients: ClientHandler = []
        self.start()

    def run(self):
        print("Server started at 127.0.0.1:9002")
        MessageHandler(self.msg_queue, self.clients).start() 
        while True:
            try:
                client_conn, client_addr = self.sock.accept()
                print(f"Client with address {client_addr} connected!")
                client_handler = ClientHandler(client_conn, self.msg_queue)
                self.clients.append(client_handler)
            except Exception as e:
                print(f"Server caught an error {e}")
    
class ClientHandler(Thread):
    def __init__(self, conn: socket.socket, msg_queue: Queue, room_name: str = '0'):
        super().__init__(daemon = True)
        self.name = "name"
        self.conn = conn
        self.msg_queue = msg_queue
        self.room_name = room_name
        self.ready = False
        self.start()
        


    def run(self):
        #self.send("Please enter your name")
        name_msg = self.recv()
        self.name = name_msg.strip()
        self.send(f"Hello, {self.name}!")

        self.ready = True
        while True:
                data: bytes = self.conn.recv(BUFFER_SIZE)
                text: str = data.decode('utf-8')
                print("received: ", text)
                date = datetime.now().strftime("%H:%M:%S")
                text = f"[{date}][{self.name}] {text}"
                self.msg_queue.put((text, self))
                data: bytes = text.encode('utf-8')
                self.conn.send(data)

    def send(self, text: str):
        try:
            self.conn.send(text.encode())
        except Exception as e:
            print(f"Send error for {self.name}: {e}")

    def recv(self):
        try:
            msg: bytes = self.conn.recv(BUFFER_SIZE)
            return msg.decode("utf-8")
        except Exception as e:
            return ""
    
class MessageHandler(Thread):
    def __init__(self, msg_queue: Queue, clients: list):
        super().__init__(daemon=True)
        self.msg_queue = msg_queue
        self.clients = clients

    def run(self):
        while True:
            try:
                message, sender = self.msg_queue.get()
                print(f"Broadcasting: {message}")
                for client in self.clients:  
                    if client != sender and client.is_alive():
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
