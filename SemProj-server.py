import socket
import pickle
from threading import Thread, Timer
from datetime import datetime
import random
import time

BUFFER_SIZE = 65536

class RoomHandler:
    def __init__(self, room_id):
        self.room_id = room_id
        self.clients = []
        self.timer = None
        self.exchange_scheduled = False

    #adding clients to check if the room is full or not
    def add_client(self, client):
        if len(self.clients) < 2:
            self.clients.append(client)
            client.current_room = self.room_id
            return True
        return False

    def is_full(self):
        return len(self.clients) == 2

    def remove_client(self, client):
        if client in self.clients:
            self.clients.remove(client)
            client.current_room = None

    def start_timer(self):
        if self.is_full() and not self.exchange_scheduled:
            self.exchange_scheduled = True
            # start timer for 45 seconds
            self.timer = Timer(45.0, self.exchange_drawings)
            self.timer.start()
            
            #notify both clients
            for client in self.clients:
                timer_msg = {'type': 'timer_start', 'data': self.room_id}
                try:
                    #dumps() serializes the element and writes it to a file in binary format
                    #convenient for direct saving of data to a file
                    #so using it
                    client.conn.send(pickle.dumps(timer_msg))
                except:
                    pass

    def exchange_drawings(self):
        if len(self.clients) == 2:
            client1, client2 = self.clients
            
            # check if both clients have drawings
            if client1.current_drawing and client2.current_drawing:
                print(f"Exchanging drawings in room {self.room_id}")
                
                # send client2 drawing to client1
                drawing_msg1 = {
                    'type': 'drawing_exchange',
                    'data': {
                        'image_data': client2.current_drawing,
                        'username': client2.name
                    }
                }
                
                # and visa versa :)
                drawing_msg2 = {
                    'type': 'drawing_exchange', 
                    'data': {
                        'image_data': client1.current_drawing,
                        'username': client1.name
                    }
                }
                
                try:
                    client1.conn.send(pickle.dumps(drawing_msg1))
                    client2.conn.send(pickle.dumps(drawing_msg2))
                    print(f"Successfully exchanged drawings in room {self.room_id}")
                except Exception as e:
                    print(f"Error sending drawings in room {self.room_id}: {e}")
            
            #reset drawings and set timer for next exchange
            for client in self.clients:
                client.current_drawing = None
            
            #next exchange
            self.exchange_scheduled = False
            self.start_timer()

class Server(Thread):
    def __init__(self, address: str, port: int):
        super().__init__(daemon=True)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((address, port))
        self.sock.listen()
        self.clients = []
        self.rooms = {}  # room_id to RoomHandler object
        self.start()

    def run(self):
        print("Server started at 127.0.0.1:9003")
        
        while True:
            try:
                client_conn, client_addr = self.sock.accept()
                print(f"Client with address {client_addr} connected!")
                client_handler = ClientHandler(client_conn, self)
                self.clients.append(client_handler)
                
            except Exception as e:
                print(f"Server error: {e}")

    def get_or_create_room(self, room_id):
        if room_id not in self.rooms:
            self.rooms[room_id] = RoomHandler(room_id)
        return self.rooms[room_id]

    def remove_empty_rooms(self):
        empty_rooms = [room_id for room_id, room in self.rooms.items() if len(room.clients) == 0]
        for room_id in empty_rooms:
            if room_id in self.rooms:
                if self.rooms[room_id].timer:
                    self.rooms[room_id].timer.cancel()
                del self.rooms[room_id]

class ClientHandler(Thread):
    def __init__(self, conn, server):
        super().__init__(daemon=True)
        self.conn = conn
        self.server = server
        self.name = "Unknown"
        self.current_drawing = None
        self.current_room = None
        self.start()

    def run(self):
        try:
            # getting a username
            name_data = self.conn.recv(1024)
            self.name = name_data.decode('utf-8').strip()
            print(f"Client registered as: {self.name}")
            
            # greetings
            welcome_msg = {'type': 'system', 'data': f"Hello, {self.name}! Use /room <room_id> to join a room."}
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
                    #converts a byte string representing a serialized object back to the original object in memory
                    message = pickle.loads(data)
                    self.process_message(message)
                except Exception as e:
                    print(f"Error decoding message: {e}")
                    
        except Exception as e:
            print(f"Client {self.name} error: {e}")
        finally:
            self.leave_room()
            if self in self.server.clients:
                self.server.clients.remove(self)
            # informing others about person who leaves the chat
            leave_msg = {'type': 'system', 'data': f"{self.name} left the chat!"}
            self.broadcast(leave_msg, include_self=False)
            self.server.remove_empty_rooms()
            print(f"Client {self.name} disconnected")

    def broadcast(self, message, include_self=False):
        #sends messages to everyone
        for client in self.server.clients:
            if client != self or include_self:
                try:
                    client.conn.send(pickle.dumps(message))
                except:
                    pass

    def broadcast_to_room(self, message, include_self=False):
        #sends messages to everyone in the same room
        if self.current_room and self.current_room in self.server.rooms:
            room = self.server.rooms[self.current_room]
            for client in room.clients:
                if client != self or include_self:
                    try:
                        client.conn.send(pickle.dumps(message))
                    except:
                        pass

    def leave_room(self):
        if self.current_room and self.current_room in self.server.rooms:
            room = self.server.rooms[self.current_room]
            room.remove_client(self)
            
            # notify room members
            leave_msg = {'type': 'system', 'data': f"{self.name} left room {self.current_room}"}
            self.broadcast_to_room(leave_msg, include_self=False)
            
            print(f"Client {self.name} left room {self.current_room}")

    def process_message(self, message):
        msg_type = message.get('type')
        data = message.get('data')
        
        if msg_type == 'chat':
            if self.current_room:
                # send to room only
                chat_msg = {
                    'type': 'chat', 
                    'data': {
                        'text': data,
                        'username': self.name,
                        'timestamp': datetime.now().strftime('%H:%M:%S')
                    }
                }
                self.broadcast_to_room(chat_msg, include_self=True)
            else:
                # send to everyone (global chat)
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
            print(f"Received drawing from {self.name} in room {self.current_room}")
            
        elif msg_type == 'join_room':
            room_id = data
            self.leave_room()  # leave current room if it exists
            
            room = self.server.get_or_create_room(room_id)
            
            if room.add_client(self):
                # successfully joined the room!!
                room_msg = {'type': 'room_joined', 'data': room_id}
                try:
                    self.conn.send(pickle.dumps(room_msg))
                except:
                    pass
                
                #notify room members
                join_msg = {'type': 'system', 'data': f"{self.name} joined room {room_id}"}
                self.broadcast_to_room(join_msg, include_self=True)
                
                print(f"Client {self.name} joined room {room_id}")
                
                # check if room is full and start timer
                if room.is_full():
                    full_msg = {'type': 'room_full', 'data': room_id}
                    for client in room.clients:
                        try:
                            client.conn.send(pickle.dumps(full_msg))
                        except:
                            pass
                    room.start_timer()
            else:
                # when somebody tryna access the room that is full
                error_msg = {'type': 'error', 'data': f"Room {room_id} is full (max 2 players)"}
                try:
                    self.conn.send(pickle.dumps(error_msg))
                except:
                    pass

if __name__ == '__main__':
    server = Server("127.0.0.1", 9003)
    
    try:
        while True:
            input("Press enter to stop the server\n")
            break
    except KeyboardInterrupt:
        print("Server stopped!")