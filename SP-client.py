import sys
import socket
from threading import Thread
from queue import SimpleQueue
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSlot, pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QMainWindow, QLineEdit, QTextEdit, \
QPushButton, QWidget, QGridLayout, QHBoxLayout, QLabel, QMessageBox

class Communication(QObject):
    msg_signal = pyqtSignal(str)

class SocketCommunication(Thread):
    def __init__(self, comm: Communication):
        super().__init__(daemon = True)
        self.comm = comm
        self.queue = SimpleQueue()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(('127.0.0.1', 9002))
        self.start()

    def run(self):

        while True: # разделить на 2 потока сенд и ресив. свой класс для каждого, демон потоки
            msg: str = self.queue.get()
            data:bytes = msg.encode('utf-8')
            self.sock.send(data)
            data: bytes = self.sock.recv(1024) 
            msg: str = data.decode('utf-8')
            self.comm.msg_signal.emit(msg)

class Canvas(QtWidgets.QLabel):
    def __init__(self):
        super().__init__()
        pixmap = QtGui.QPixmap(600, 600)
        pixmap.fill(Qt.white)
        self.setPixmap(pixmap)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)  
        self.setMinimumSize(600, 600) 

        self.last_x, self.last_y = None, None
        self.pen_color = QtGui.QColor('#000000')
    
    def setPenColor(self, color):
        self.pen_color = QtGui.QColor(color)
    
    def mouseMoveEvent(self, event):
        pos = event.pos()
        x, y = pos.x(), pos.y()
        
        pixmap = self.pixmap()
        if pixmap:
            if x < 0: 
                x = 0

            if y < 0: 
                y = 0

            if x >= pixmap.width():
                x = pixmap.width() - 1

            if y >= pixmap.height():
                y = pixmap.height() - 1
        
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
    
    def mouseReleaseEvent(self, event):
        self.last_x = None
        self.last_y = None
    
colors = ['#000000', '#141923', '#414168', '#3a7fa7', '#35e3e3', '#8fd970', '#5ebb49',
'#458352', '#dcd37b', '#fffee5', '#ffd035', '#cc9245', '#a15c3e', '#a42f3b',
'#f45b7a', '#c24998', '#81588d', '#bcb0c2', '#ffffff',
]

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
        self.set_gui()  
        self.show()

    def set_gui(self):  
        self.color = 'gray'
        self.setWindowTitle("drawer")
        self.setMinimumWidth(800)
        self.setMinimumHeight(800)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        self.horizontal_layout = QHBoxLayout(central_widget)  
        
        #here chat settings
        self.chat_grid_layout = QGridLayout()
        
        self.game_grid_layout = QtWidgets.QVBoxLayout() 

        self.btn_send = QPushButton()
        self.btn_send.setText("send")
        self.btn_send.clicked.connect(self.event_send)
        self.comm.msg_signal.connect(self.event_recv)

        self.output_area = QTextEdit()

        self.input_field = QLineEdit()

        self.input_field.setPlaceholderText("Write a text")
        self.output_area.setReadOnly(True)

        self.output_area.setStyleSheet("color: midnightblue;"
                                       "border: 2px solid midnightblue;")
        self.output_area.setText("Please enter your name")

        self.input_field.setStyleSheet("border: 2px solid midnightblue;")
        self.btn_send.setStyleSheet("border: 2px solid midnightblue; "
                                "font-weight: bold;"
                                "border-radius: 5px; "
                                "background-color: wheat;")

        self.chat_grid_layout.addWidget(self.output_area, 0, 0, 3, 4)
        self.chat_grid_layout.addWidget(self.input_field, 3, 0, 1, 3)
        self.chat_grid_layout.addWidget(self.btn_send, 3, 3, 1, 1)

        palette = QtWidgets.QHBoxLayout()
        self.add_palette_buttons(palette)
        self.game_grid_layout.addWidget(self.canvas)
        self.game_grid_layout.addLayout(palette)

        self.horizontal_layout.addLayout(self.game_grid_layout)
        self.horizontal_layout.addLayout(self.chat_grid_layout)

    @pyqtSlot()  
    def event_send(self):
        text = self.input_field.text()
        self.input_field.setText('')
        self.sock_comm.queue.put(text)  
        # print(f"Send: {text}")  
        

    @pyqtSlot(str)  
    def event_recv(self, text: str):
        text = f"<span style='color: midnightblue'>{text}</span>"  
        self.output_area.append(text)

    def add_palette_buttons(self, layout):
        for color in colors:
            btn = QPaletteButton(color)
            btn.pressed.connect(lambda c=color: self.canvas.setPenColor(c))
            layout.addWidget(btn)


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()
app.exec_()
#QtBrush u QtPen
#3д матрица пикселей