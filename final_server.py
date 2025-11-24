import socket
import pickle
from threading import Thread
from datetime import datetime
import random
import time

BUFFER_SIZE = 65536

class Server(Thread):
    def __init__(self, address: str, port: int):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((address, port))
        self.sock.listen()
        self.clients = []
        self.drawings = {}  # stores the users drawings
        self.start()

    def run(self):
        print("Server started at 127.0.0.1:9003")
        
        # executing a timer for drawings exchange
        exchange_thread = Thread(target=self.exchange_loop, daemon=True)
        exchange_thread.start()
        
        while True:
            try:
                client_conn, client_addr = self.sock.accept()
                print(f"Client with address {client_addr} connected!")
                client_handler = ClientHandler(client_conn, self)
                self.clients.append(client_handler)
                
            except Exception as e:
                print(f"Server error: {e}")

    def exchange_loop(self):
        #loop for drawings exchange every 45 sec
        while True:
            time.sleep(45) 
            if len(self.clients) >= 2: #we cannot start a game with only one player :))
                print("Starting drawing exchange...")
                self.exchange_drawings()

    def exchange_drawings(self):
        #changes the drawings between players
        if len(self.clients) < 2:
            return
            
        # a dictionary with all current drawings 
        current_drawings = {}
        for client in self.clients:
            if hasattr(client, 'current_drawing') and client.current_drawing: #if the current drawing != None
                current_drawings[client] = client.current_drawing
                print(f"Collected drawing from {client.name}")
        
        if len(current_drawings) < 2:
            print("Not enough drawings for exchange :( )")
            return
            
        # Создаем пары случайным образом
        players_with_drawings = list(current_drawings.keys())
        random.shuffle(players_with_drawings)
        
        # Обмениваем рисунками между парами
        for i in range(0, len(players_with_drawings), 2):
            if i + 1 < len(players_with_drawings):
                client1 = players_with_drawings[i]
                client2 = players_with_drawings[i + 1]
                
                drawing1 = current_drawings[client1]
                drawing2 = current_drawings[client2]
                
                print(f"Exchanging drawings between {client1.name} and {client2.name}")
                
                # Отправляем рисунок client2 клиенту client1
                drawing_msg1 = {
                    'type': 'drawing_exchange',
                    'data': {
                        'image_data': drawing2,  # Отправляем рисунок второго игрока первому
                        'username': client2.name
                    }
                }
                
                # Отправляем рисунок client1 клиенту client2
                drawing_msg2 = {
                    'type': 'drawing_exchange', 
                    'data': {
                        'image_data': drawing1,  # Отправляем рисунок первого игрока второму
                        'username': client1.name
                    }
                }
                
                try:
                    client1.conn.send(pickle.dumps(drawing_msg1))
                    client2.conn.send(pickle.dumps(drawing_msg2))
                    print(f"Successfully exchanged drawings between {client1.name} and {client2.name}")
                except Exception as e:
                    print(f"Error sending drawings: {e}")
        
        # Очищаем рисунки после обмена
        for client in self.clients:
            client.current_drawing = None

class ClientHandler(Thread):
    def __init__(self, conn, server):
        super().__init__(daemon=True)
        self.conn = conn
        self.server = server
        self.name = "Unknown"
        self.current_drawing = None
        self.start()

    def run(self):
        try:
            # getting a username
            name_data = self.conn.recv(1024)
            self.name = name_data.decode('utf-8').strip()
            print(f"Client registered as: {self.name}")
            
            # greetings
            welcome_msg = {'type': 'system', 'data': f"Hello, {self.name}!"}
            self.conn.send(pickle.dumps(welcome_msg))
            
            # "meet-a-new-user" message
            join_msg = {'type': 'system', 'data': f"{self.name} joined the chat!"}
            self.broadcast(join_msg, include_self=True)
            
            # main loop
            while True:
                data = self.conn.recv(BUFFER_SIZE)
                if not data:
                    break
                    
                try:
                    message = pickle.loads(data)
                    self.process_message(message)
                except Exception as e:
                    print(f"Error decoding message: {e}")
                    
        except Exception as e:
            print(f"Client {self.name} error: {e}")
        finally:
            if self in self.server.clients:
                self.server.clients.remove(self)
            # informing others about person who leaves the chat
            leave_msg = {'type': 'system', 'data': f"{self.name} left the chat!"}
            self.broadcast(leave_msg, include_self=False)
            print(f"Client {self.name} disconnected")

    def broadcast(self, message, include_self=False):
        #sends messages to everyone
        for client in self.server.clients:
            if client != self or include_self:
                try:
                    client.conn.send(pickle.dumps(message))
                except:
                    pass

    def process_message(self, message):
        msg_type = message.get('type')
        data = message.get('data')
        
        if msg_type == 'chat':
            # message sending
            chat_msg = {
                'type': 'chat', 
                'data': {
                    'text': data,
                    'username': self.name,
                    'timestamp': datetime.now().strftime('%H:%M:%S')
                }
            }
            self.broadcast(chat_msg, include_self=True)
                        
        elif msg_type == 'drawing_ready':
            # saving a drawing for exchange
            self.current_drawing = data
            print(f"Received drawing from {self.name} for exchange")

if __name__ == '__main__':
    server = Server("127.0.0.1", 9003)
    
    try:
        while True:
            input("Press enter to stop the server\n")
            break
    except KeyboardInterrupt:
        print("Server stopped!")