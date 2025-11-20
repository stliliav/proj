import sys
import socket
from threading import Thread
from queue import SimpleQueue
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QTextEdit, \
QPushButton, QWidget, QGridLayout, QHBoxLayout, QLabel, QInputDialog

class Communication(QObject):
    msg_signal = pyqtSignal(str)

class SendThread(Thread):
    def __init__(self, sock, queue):
        super().__init__(daemon=True)
        self.sock = sock
        self.queue = queue
        self.running = True

    def run(self):
        while self.running:
            msg = self.queue.get()
            if msg == "EXIT":
                break
            try:
                self.sock.send(msg.encode('utf-8'))
                print(f"Sent: {msg}")
            except Exception as e:
                print(f"Send error: {e}")
                break

class ReceiveThread(Thread):
    def __init__(self, sock, comm):
        super().__init__(daemon=True)
        self.sock = sock
        self.comm = comm
        self.running = True

    def run(self):
        while self.running:
            try:
                data = self.sock.recv(1024)
                if not data:
                    break
                msg = data.decode('utf-8')
                self.comm.msg_signal.emit(msg)
                print(f"Received: {msg}")
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break

class SocketCommunication:
    def __init__(self, comm):
        self.comm = comm
        self.queue = SimpleQueue()
        self.sock = None
        self.send_thread = None
        self.receive_thread = None

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(('127.0.0.1', 9002))
            print("Connected to server")
            
            # name request
            data = self.sock.recv(1024)
            welcome_msg = data.decode('utf-8')
            self.comm.msg_signal.emit(welcome_msg)
            
            # has the user input his name? :)
            name, ok = QInputDialog.getText(None, "Name", "Enter your name:")
            if ok and name:
                self.sock.send(name.encode('utf-8'))
            else:
                self.sock.send("user".encode('utf-8'))
            
            # greeting: hello, name!
            data = self.sock.recv(1024)
            hello_msg = data.decode('utf-8')
            self.comm.msg_signal.emit(hello_msg)
            
            # start the threasd
            self.send_thread = SendThread(self.sock, self.queue)
            self.receive_thread = ReceiveThread(self.sock, self.comm)
            self.send_thread.start()
            self.receive_thread.start()
            
            #boolean to know if we connected or sth went wrong??
            return True
            
        except Exception as e:
            print(f"Connection error: {e}")
            self.comm.msg_signal.emit(f"Connection failed: {e}")
            return False

    def send_message(self, text):
        #if our thread successfully started and working(alive), we are working with incoming text
        if self.send_thread and self.send_thread.is_alive():
            self.queue.put(text)
            return True
        return False

    def disconnect(self):
        if self.send_thread:
            self.send_thread.running = False
            self.queue.put("EXIT")
        if self.receive_thread:
            self.receive_thread.running = False
        try:
            if self.sock:
                self.sock.close()
        except:
            pass

#the whole class for a "Paint" part
class Canvas(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        pixmap = QtGui.QPixmap(600, 600)
        pixmap.fill(Qt.white) #set background color
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft) # make it placed on the left side of the window, on the right we'll have chat 
        self.setMinimumSize(600, 600) #not to ruin the size ratio 

        #actually, the line is a set of close-standing points.
        # to make line unbreakable, we will draw a new point where the previous finishes
        # that's why we have to store the last coordinates:
        self.last_x, self.last_y = None, None 

        self.pen_color = QtGui.QColor('#000000') #set black pen color by default
    
    #make a pen color changeable 
    def setPenColor(self, color):
        self.pen_color = QtGui.QColor(color)
    
    #line goes where the cursor does
    def mouseMoveEvent(self, event):
        pos = event.pos() #current coordinates of a cursor
        x, y = pos.x(), pos.y()
        
        #pixmap helps to work with images

        pixmap = self.pixmap()
        #checks. are we drawing inside the widget's borders?
        if pixmap:
            if x < 0: x = 0
            if y < 0: y = 0
            if x >= pixmap.width(): x = pixmap.width() - 1
            if y >= pixmap.height(): y = pixmap.height() - 1
        
        if self.last_x is None:
            self.last_x = x
            self.last_y = y
            return 
        
        painter = QtGui.QPainter(self.pixmap())
        p = painter.pen()
        p.setWidth(4)
        p.setColor(self.pen_color)
        painter.setPen(p)
        painter.drawLine(self.last_x, self.last_y, x, y)
        painter.end()
        self.update()

        self.last_x = x
        self.last_y = y
    
    #occurs when we stop pressing on cursor
    def mouseReleaseEvent(self, event):
        self.last_x = None
        self.last_y = None
    
colors = ['#000000', '#141923', '#414168', '#3a7fa7', '#35e3e3', '#8fd970', '#5ebb49',
'#458352', '#dcd37b', '#fffee5', '#ffd035', '#cc9245', '#a15c3e', '#a42f3b',
'#f45b7a', '#c24998', '#81588d', '#bcb0c2', '#ffffff',
]

#this class makes widgets(buttons) with colors. if you click on them, the pen will change its color
class QPaletteButton(QtWidgets.QPushButton):
    def __init__(self, color):
        super().__init__()
        self.setFixedSize(QtCore.QSize(24, 24))
        self.color = color
        self.setStyleSheet("background-color: %s;" % color)

#getting all the interface together on a main window
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.comm = Communication()
        self.canvas = Canvas()
        self.sock_comm = SocketCommunication(self.comm)
        
        self.set_gui()  
        
        # connecting afer GUI creation
        if not self.sock_comm.connect():
            #critical for making a "brighter" message box. it will have a red crossed circle on it and a message
            QtWidgets.QMessageBox.critical(self, "Error", "Failed to connect to server")
        
        self.show()

    #basic window settings
    def set_gui(self):  
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
        #set what happens wher we are clicking on the "send" button
        self.btn_send.clicked.connect(self.event_send)
        self.comm.msg_signal.connect(self.event_recv)

        self.output_area = QTextEdit()
        self.input_field = QLineEdit()

        self.input_field.setPlaceholderText("Write your text")
        self.output_area.setReadOnly(True) #we cannot change what we have already written!

        self.output_area.setStyleSheet("color: midnightblue; border: 2px solid midnightblue;")
        self.input_field.setStyleSheet("border: 2px solid midnightblue;")
        self.btn_send.setStyleSheet("border: 2px solid midnightblue; font-weight: bold; border-radius: 5px; background-color: wheat;")

        self.chat_grid_layout.addWidget(self.output_area, 0, 0, 3, 4)
        self.chat_grid_layout.addWidget(self.input_field, 3, 0, 1, 3)
        self.chat_grid_layout.addWidget(self.btn_send, 3, 3, 1, 1)

        palette = QtWidgets.QHBoxLayout()
        self.add_palette_buttons(palette)
        self.game_grid_layout.addWidget(self.canvas)
        self.game_grid_layout.addLayout(palette)

        self.horizontal_layout.addLayout(self.game_grid_layout)
        self.horizontal_layout.addLayout(self.chat_grid_layout)
    #user disconnection
    def closeEvent(self, event):
        self.sock_comm.disconnect()
        event.accept()

    @pyqtSlot()  
    def event_send(self):
        text = self.input_field.text().strip() #remove extra spaces and chars before and after the message
        if text:
            self.input_field.setText('')
            #if not succeeded in message sending
            if not self.sock_comm.send_message(text):
                self.output_area.append("<span style='color: red'>Not connected</span>")

    @pyqtSlot(str)  
    #for the better look, setting the greeting message with another color
    def event_recv(self, text: str):
        if "Hello" in text:
            color = "green"
        else:
            color = "midnightblue"
        text = f"<span style='color: {color}'>{text}</span>"  
        self.output_area.append(text)

    def add_palette_buttons(self, layout):
        for color in colors:
            btn = QPaletteButton(color)
            btn.pressed.connect(lambda c=color: self.canvas.setPenColor(c))
            layout.addWidget(btn)

app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
app.exec_()