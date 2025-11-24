import sys
import socket
import pickle
import base64
from threading import Thread
from queue import SimpleQueue
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QTextEdit, \
QPushButton, QWidget, QGridLayout, QHBoxLayout, QLabel, QInputDialog, QMessageBox

class Communication(QObject):
    msg_signal = pyqtSignal(dict)

class SocketCommunication(QObject):

    def __init__(self, comm: Communication):
        super().__init__()
        self.comm = comm
        self.queue = SimpleQueue()
        self.sock = None
        self.running = False
        self.send_thread = None
        self.receive_thread = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(('127.0.0.1', 9003))
            print("Connected to server")
            
            # name request in a separate window 
            name, ok = QInputDialog.getText(None, "Name", "Enter your name:")
            if ok and name:
                self.sock.send(name.encode('utf-8'))
            else:
                self.sock.send("Anonymous".encode('utf-8'))
            
            # greetings!!
            data = self.sock.recv(1024)
            #converts a byte string representing a serialized object back to the original object in memory
            welcome_msg = pickle.loads(data)
            self.comm.msg_signal.emit(welcome_msg)
            
            # threads execution
            self.running = True
            self.receive_thread = Thread(target=self.receive_messages, daemon=True)
            self.send_thread = Thread(target=self.send_messages, daemon=True)
            self.receive_thread.start()
            self.send_thread.start()

            #boolean return to know if we connected or sth went wrong??
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            error_msg = {'type': 'error', 'data': f"Connection failed: {e}"}
            self.comm.msg_signal.emit(error_msg)
            return False

    def receive_messages(self):
        while self.running:
            try:
                data = self.sock.recv(65536)
                if not data:
                    break
                #converts a byte string representing a serialized object back to the original object in memory
                message = pickle.loads(data)

                # emit() generates a signal for data tranferring to the main thread
                self.comm.msg_signal.emit(message)
            except Exception as e:
                #if didnt break yet throwing mistakes
                if self.running:
                    print(f"Receive error: {e}")
                break

    def send_messages(self):
        while self.running:
            try:
                message = self.queue.get()
                if message == "EXIT":
                    break
                #returns a serialized representation of an object as a sequence of bytes
                self.sock.send(pickle.dumps(message))
            except Exception as e:
                print(f"Send error: {e}")
                break

    def send_message(self, message_type, data):
        if self.running:
            message = {'type': message_type, 'data': data}
            self.queue.put(message)

    def disconnect(self):
        self.running = False
        self.queue.put("EXIT")
        try:
            if self.sock:
                self.sock.close()
        except:
            pass

#the whole gui class :)
class Canvas(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        self.setup_canvas()
        self.current_color = '#000000'
        self.last_x, self.last_y = None, None
    
    def setup_canvas(self):
        pixmap = QtGui.QPixmap(600, 600)
        pixmap.fill(Qt.white) #background color
        self.setPixmap(pixmap) #simple pixel map
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)  #i want painter side to be in the left
        self.setMinimumSize(600, 600)

    def setPenColor(self, color):
        self.current_color = color

    #line goes where the cursor does
    def mouseMoveEvent(self, event):
        if self.last_x is None:
            self.last_x = event.x()
            self.last_y = event.y()
            return 
        
        painter = QtGui.QPainter(self.pixmap())
        p = painter.pen()
        p.setWidth(4)
        p.setColor(QtGui.QColor(self.current_color))
        painter.setPen(p)
        painter.drawLine(self.last_x, self.last_y, event.x(), event.y())
        painter.end()
        self.update()

        #actually, the line is a set of close-standing points.
        # to make line unbreakable, we will draw a new point where the previous finishes
        # that's why we have to store the last coordinates:
        self.last_x = event.x()
        self.last_y = event.y()
    
    def mouseReleaseEvent(self, event):
        self.last_x = None
        self.last_y = None

    def to_base64(self):
        """Конвертирует QPixmap в base64"""
        #function converts QPixmap into base64
        #Base64 is a system for encoding binary data into a text format using only 64 ASCII characters!
        try:
            qimage = self.pixmap().toImage()
            buffer = QtCore.QBuffer()
            buffer.open(QtCore.QIODevice.ReadWrite)
            qimage.save(buffer, "PNG")
            data = buffer.data()
            return base64.b64encode(data).decode('utf-8')
        except Exception as e:
            print(f"Error converting to base64: {e}")
            return ""

    def from_base64(self, base64_string):
        #loads base64 to QPixmap
        try:
            image_data = base64.b64decode(base64_string)
            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(image_data)
            self.setPixmap(pixmap)
        except Exception as e:
            print(f"Error loading from base64: {e}")

colors = ['#000000', '#141923', '#414168', '#3a7fa7', '#35e3e3', '#8fd970', '#5ebb49',
'#458352', '#dcd37b', '#fffee5', '#ffd035', '#cc9245', '#a15c3e', '#a42f3b',
'#f45b7a', '#c24998', '#81588d', '#bcb0c2', '#ffffff',]

#color palette with buttons
class QPaletteButton(QtWidgets.QPushButton):
    def __init__(self, color):
        super().__init__()
        self.setFixedSize(QtCore.QSize(24, 24))
        self.color = color
        self.setStyleSheet("background-color: %s;" % color)

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.canvas = Canvas()
        
        self.sock_comm = SocketCommunication(self.comm)
        
        self.swap_timer = QtCore.QTimer()
        self.swap_timer.timeout.connect(self.send_current_drawing)
        
        self.set_gui()  
        
        # Connecting after GUI creation
        if self.sock_comm.connect():
            self.swap_timer.start(45000)  # 45 sec
        
        self.show()

    def set_gui(self): 
        #basic window settings 
        self.setWindowTitle("drawer")
        self.setMinimumWidth(800)
        self.setMinimumHeight(800)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        self.horizontal_layout = QHBoxLayout(central_widget)  
        
        #chat settings
        self.chat_grid_layout = QGridLayout()
        self.game_grid_layout = QtWidgets.QVBoxLayout() 

        self.btn_send = QPushButton()
        self.btn_send.setText("send")
        self.btn_send.clicked.connect(self.event_send)
        self.comm.msg_signal.connect(self.event_recv)

        self.output_area = QTextEdit()
        self.input_field = QLineEdit()

        #setting a placeholder!
        self.input_field.setPlaceholderText("Write your text")

        #chat cannot be edited
        self.output_area.setReadOnly(True)

        self.output_area.setStyleSheet("color: midnightblue; border: 2px solid midnightblue;")
        self.input_field.setStyleSheet("border: 2px solid midnightblue;")
        self.btn_send.setStyleSheet("border: 2px solid midnightblue; font-weight: bold; border-radius: 5px; background-color: wheat;")

        self.chat_grid_layout.addWidget(self.output_area, 0, 0, 3, 4)
        self.chat_grid_layout.addWidget(self.input_field, 3, 0, 1, 3)
        self.chat_grid_layout.addWidget(self.btn_send, 3, 3, 1, 1)

        #and setting color palette
        palette = QtWidgets.QHBoxLayout()
        self.add_palette_buttons(palette)
        self.game_grid_layout.addWidget(self.canvas)
        self.game_grid_layout.addLayout(palette)

        self.horizontal_layout.addLayout(self.game_grid_layout)
        self.horizontal_layout.addLayout(self.chat_grid_layout)

    #disconnection
    def closeEvent(self, event):
        self.sock_comm.disconnect()
        event.accept()

    def send_current_drawing(self):
        #sends a current drawing to the server for exchange
        try:
            drawing_base64 = self.canvas.to_base64()
            if drawing_base64:
                self.sock_comm.send_message('drawing_ready', drawing_base64)
                self.output_area.append("<span style='color: orange'>Your drawing has been sent for exchange!</span>")
        except Exception as e:
            print(f"Error sending drawing: {e}")

    @pyqtSlot()  
    def event_send(self):
        text = self.input_field.text().strip() #remove extra chars form a msg (e.g. spaces in front of the text)
        if text:
            self.input_field.setText('')
            self.sock_comm.send_message('chat', text)

    @pyqtSlot(dict)  
    #design acc. to the type of the msg
    def event_recv(self, message):

        msg_type = message.get('type')
        data = message.get('data')
        
        if msg_type == 'system':
            self.output_area.append(f"<span style='color: green'>{data}</span>")
        elif msg_type == 'error':
            self.output_area.append(f"<span style='color: red'>Error: {data}</span>")
        elif msg_type == 'chat':
            color = "midnightblue"
            text = f"<span style='color: {color}'><b>{data['username']}</b> [{data['timestamp']}]: {data['text']}</span>"
            self.output_area.append(text)
        elif msg_type == 'drawing_exchange':
            try:
                # replace a current canva with a given one
                self.canvas.from_base64(data['image_data'])
                self.output_area.append(f"<span style='color: green'>You received a drawing from {data['username']}!</span>")
                self.output_area.append("<span style='color: orange'>Continue drawing on the received canvas!</span>")
            except Exception as e:
                print(f"Error loading drawing: {e}")
    
    #color palette buttons! if click, pen will change its color
    def add_palette_buttons(self, layout):
        for color in colors:
            btn = QPaletteButton(color)
            btn.pressed.connect(lambda c=color: self.canvas.setPenColor(c))
            layout.addWidget(btn)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    app.exec_()