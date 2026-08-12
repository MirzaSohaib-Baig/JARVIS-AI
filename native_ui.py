"""
JARVIS desktop shell (PyQt6) — Mark-L UI edition with HUD Canvas.
Integrated with orchestrator.py for full AI chat capabilities.

Run with:
    python main_qt.py

First run: pip install PyQt6 PyQt6-WebEngine qasync
"""

from __future__ import annotations

import asyncio
import atexit
import json
import math
import os
import platform
import random
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt6.QtCore import (
    QEasingCurve, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal, pyqtSlot
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont, QFontDatabase, QKeySequence,
    QPainter, QPainterPath, QPen, QPixmap, QRadialGradient, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar,
)

# Import the orchestrator
try:
    from brain.orchestrator import handle_message as orchestrator_handle_message
    ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    print(f"Warning: orchestrator not available - {e}")
    ORCHESTRATOR_AVAILABLE = False


_OS = platform.system()


# ─── JARVIS Color Palette (Mark-L style) ────────────────────────────────
class C:
    BG        = "#00060a"
    PANEL     = "#010d14"
    PANEL2    = "#010f18"
    BORDER    = "#0d3347"
    BORDER_B  = "#1a5c7a"
    BORDER_A  = "#0f4060"
    PRI       = "#00d4ff"
    PRI_DIM   = "#007a99"
    PRI_GHO   = "#001f2e"
    ACC       = "#ff6b00"
    ACC2      = "#ffcc00"
    GREEN     = "#00ff88"
    GREEN_D   = "#00aa55"
    RED       = "#ff3355"
    MUTED_C   = "#ff3366"
    TEXT      = "#8ffcff"
    TEXT_DIM  = "#3a8a9a"
    TEXT_MED  = "#5ab8cc"
    WHITE     = "#d8f8ff"
    DARK      = "#000d14"
    BAR_BG    = "#011520"


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h); c.setAlpha(a); return c


# ─── HUD Canvas (Mark-L style animated circular HUD) ────────────────────
class HudCanvas(QWidget):
    """Animated JARVIS-style circular HUD display."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted    = False
        self.speaking = False
        self.state    = "INITIALISING"
        self._assistant_name = "J.A.R.V.I.S"

        self._tick       = 0
        self._scale      = 1.0
        self._tgt_scale  = 1.0
        self._halo       = 55.0
        self._tgt_halo   = 55.0
        self._last_t     = time.time()
        self._scan       = 0.0
        self._scan2      = 180.0
        self._rings      = [0.0, 120.0, 240.0]
        self._pulses: list[float] = [0.0, 50.0, 100.0]
        self._blink      = True
        self._blink_tick = 0
        self._particles: list[list[float]] = []

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)

    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.06, 1.14)
                self._tgt_halo  = random.uniform(145, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo  = random.uniform(15, 28)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo  = random.uniform(48, 68)
            self._last_t = now

        sp = 0.38 if self.speaking else 0.15
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo  += (self._tgt_halo  - self._halo)  * sp

        speeds = [1.3, -0.9, 2.0] if self.speaking else [0.55, -0.35, 0.9]
        for i, spd in enumerate(speeds):
            self._rings[i] = (self._rings[i] + spd) % 360

        self._scan  = (self._scan  + (3.0 if self.speaking else 1.3)) % 360
        self._scan2 = (self._scan2 + (-2.0 if self.speaking else -0.75)) % 360

        fw  = min(self.width(), self.height())
        lim = fw * 0.74
        spd = 4.2 if self.speaking else 2.0
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.07 if self.speaking else 0.025):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.28:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            r_s = fw * 0.28
            self._particles.append([
                cx + math.cos(ang) * r_s, cy + math.sin(ang) * r_s,
                math.cos(ang) * random.uniform(0.9, 2.4),
                math.sin(ang) * random.uniform(0.9, 2.4) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0]+p[2], p[1]+p[3], p[2]*0.97, p[3]*0.97, p[4]-0.028]
            for p in self._particles if p[4] > 0
        ]

        self._blink_tick += 1
        if self._blink_tick >= 38:
            self._blink = not self._blink
            self._blink_tick = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), qcol(C.BG))

        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)

        # grid dots
        p.setPen(QPen(qcol(C.PRI_GHO), 1))
        for x in range(0, W, 48):
            for y in range(0, H, 48):
                p.drawPoint(x, y)

        r_face = fw * 0.31

        # halo glow
        for i in range(10):
            r   = r_face * (1.8 - i * 0.08)
            frc = 1.0 - i / 10
            a   = max(0, min(255, int(self._halo * 0.085 * frc)))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # pulse rings
        for pr in self._pulses:
            a   = max(0, int(230 * (1.0 - pr / (fw * 0.74))))
            col = qcol(C.MUTED_C if self.muted else C.PRI, a)
            p.setPen(QPen(col, 1.5)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - pr, cy - pr, pr * 2, pr * 2))

        # spinning arc rings
        for idx, (r_frac, w_r, arc_l, gap) in enumerate(
            [(0.48, 3, 115, 78), (0.40, 2, 78, 55), (0.32, 1, 56, 40)]
        ):
            ring_r = fw * r_frac
            base   = self._rings[idx]
            a_val  = max(0, min(255, int(self._halo * (1.0 - idx * 0.18))))
            col    = qcol(C.MUTED_C if self.muted else C.PRI, a_val)
            p.setPen(QPen(col, w_r)); p.setBrush(Qt.BrushStyle.NoBrush)
            angle = base
            rect  = QRectF(cx - ring_r, cy - ring_r, ring_r * 2, ring_r * 2)
            while angle < base + 360:
                p.drawArc(rect, int(angle * 16), int(arc_l * 16))
                angle += arc_l + gap

        # scanners
        sr = fw * 0.50
        sa = min(255, int(self._halo * 1.5))
        ex = 75 if self.speaking else 44
        p.setPen(QPen(qcol(C.MUTED_C if self.muted else C.PRI, sa), 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        srect = QRectF(cx - sr, cy - sr, sr * 2, sr * 2)
        p.drawArc(srect, int(self._scan * 16), int(ex * 16))
        p.setPen(QPen(qcol(C.ACC, sa // 2), 1.5))
        p.drawArc(srect, int(self._scan2 * 16), int(ex * 16))

        # tick marks
        t_out, t_in = fw * 0.497, fw * 0.474
        p.setPen(QPen(qcol(C.PRI, 140), 1))
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 6
            p.drawLine(
                QPointF(cx + t_out * math.cos(rad), cy - t_out * math.sin(rad)),
                QPointF(cx + inn  * math.cos(rad), cy - inn  * math.sin(rad)),
            )

        # crosshair
        ch_r, gap_h = fw * 0.51, fw * 0.16
        p.setPen(QPen(qcol(C.PRI, int(self._halo * 0.5)), 1))
        p.drawLine(QPointF(cx - ch_r, cy), QPointF(cx - gap_h, cy))
        p.drawLine(QPointF(cx + gap_h, cy), QPointF(cx + ch_r, cy))
        p.drawLine(QPointF(cx, cy - ch_r), QPointF(cx, cy - gap_h))
        p.drawLine(QPointF(cx, cy + gap_h), QPointF(cx, cy + ch_r))

        # corner brackets
        bl = 24
        bc = qcol(C.PRI, 210)
        hl, hr = cx - fw // 2, cx + fw // 2
        ht, hb = cy - fw // 2, cy + fw // 2
        p.setPen(QPen(bc, 2))
        for bx, by, dx, dy in [(hl,ht,1,1),(hr,ht,-1,1),(hl,hb,1,-1),(hr,hb,-1,-1)]:
            p.drawLine(QPointF(bx, by), QPointF(bx + dx * bl, by))
            p.drawLine(QPointF(bx, by), QPointF(bx, by + dy * bl))

        # center orb
        orb_r = int(fw * 0.27 * self._scale)
        oc    = (200, 0, 50) if self.muted else (0, 60, 110)
        for i in range(8, 0, -1):
            r2  = int(orb_r * i / 8)
            frc = i / 8
            a   = max(0, min(255, int(self._halo * 1.1 * frc)))
            p.setBrush(QBrush(QColor(int(oc[0]*frc), int(oc[1]*frc), int(oc[2]*frc), a)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(cx - r2, cy - r2, r2 * 2, r2 * 2))
        
        # Center text
        p.setPen(QPen(qcol(C.PRI, min(255, int(self._halo * 2))), 1))
        p.setFont(QFont("Courier New", 13, QFont.Weight.Bold))
        p.drawText(QRectF(cx - 80, cy - 14, 160, 28),
                   Qt.AlignmentFlag.AlignCenter, self._assistant_name)

        # particles
        for pt in self._particles:
            a = max(0, min(255, int(pt[4] * 255)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(qcol(C.PRI, a)))
            p.drawEllipse(QPointF(pt[0], pt[1]), 2.5, 2.5)

        # status text
        sy = cy + fw * 0.40
        if self.muted:
            txt, col = "⊘  MUTED",     qcol(C.MUTED_C)
        elif self.speaking:
            txt, col = "●  SPEAKING",  qcol(C.ACC)
        elif self.state == "THINKING":
            sym = "◈" if self._blink else "◇"
            txt, col = f"{sym}  THINKING",   qcol(C.ACC2)
        elif self.state == "PROCESSING":
            sym = "▷" if self._blink else "▶"
            txt, col = f"{sym}  PROCESSING", qcol(C.ACC2)
        elif self.state == "LISTENING":
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  LISTENING",  qcol(C.GREEN)
        else:
            sym = "●" if self._blink else "○"
            txt, col = f"{sym}  {self.state}", qcol(C.PRI)

        p.setPen(QPen(col, 1))
        p.setFont(QFont("Courier New", 11, QFont.Weight.Bold))
        p.drawText(QRectF(0, sy, W, 26), Qt.AlignmentFlag.AlignCenter, txt)

        # waveform
        wy = sy + 30
        N, bw = 36, 8
        wx0 = (W - N * bw) / 2
        for i in range(N):
            if self.muted:
                hgt, cl = 2, qcol(C.MUTED_C)
            elif self.speaking:
                hgt = random.randint(3, 20)
                cl  = qcol(C.PRI) if hgt > 12 else qcol(C.PRI_DIM)
            else:
                hgt = int(3 + 2 * math.sin(self._tick * 0.09 + i * 0.6))
                cl  = qcol(C.BORDER_B)
            p.fillRect(QRectF(wx0 + i * bw, wy + 20 - hgt, bw - 1, hgt), cl)


# ─── Chat Widget ────────────────────────────────────────────────────────
class ChatBubble(QFrame):
    """Individual chat message bubble."""
    
    def __init__(self, text: str, is_user: bool = False, is_pending: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        
        if is_pending:
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0, 212, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.2);
                    border-radius: 10px;
                }}
            """)
        elif is_user:
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0, 212, 255, 0.1);
                    border: 1px solid {C.PRI};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: rgba(0, 212, 255, 0.05);
                    border: 1px solid rgba(0, 212, 255, 0.3);
                    border-radius: 10px;
                }}
            """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        
        label = QLabel(text)
        label.setWordWrap(True)
        
        if is_pending:
            label.setStyleSheet(f"color: {C.TEXT_DIM}; font-family: 'Courier New'; font-size: 11px; font-style: italic;")
        elif is_user:
            label.setStyleSheet(f"color: {C.WHITE}; font-family: 'Courier New'; font-size: 11px;")
        else:
            label.setStyleSheet(f"color: {C.PRI}; font-family: 'Courier New'; font-size: 11px;")
        
        layout.addWidget(label)


class ChatWidget(QWidget):
    """Complete chat interface with history and orchestrator integration."""
    
    state_changed = pyqtSignal(str)  # Signal to update HUD state
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conversation_history = []
        self.session_id = f'qt-{int(time.time())}-{os.urandom(4).hex()}'
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        
        # Chat log
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: {C.PANEL};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                background: {C.BG};
                width: 6px;
                border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B};
                border-radius: 3px;
                min-height: 20px;
            }}
        """)
        
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.chat_layout.setSpacing(4)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        
        self.scroll_area.setWidget(self.chat_container)
        
        # Input area
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(6)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText(f"Ask JARVIS anything...")
        self.input_field.setFont(QFont("Courier New", 10))
        self.input_field.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL};
                color: {C.WHITE};
                border: 1px solid {C.BORDER};
                border-radius: 20px;
                padding: 10px 16px;
            }}
            QLineEdit:focus {{
                border-color: {C.PRI};
            }}
        """)
        
        self.send_btn = QPushButton("SEND")
        self.send_btn.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C.PRI_DIM}, stop:1 {C.PRI});
                color: {C.DARK};
                border: none;
                border-radius: 20px;
                padding: 10px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {C.PRI}, stop:1 {C.PRI});
            }}
            QPushButton:disabled {{
                background: {C.BORDER_A};
                color: {C.TEXT_DIM};
            }}
        """)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_btn)
        
        layout.addWidget(self.scroll_area)
        layout.addWidget(input_widget)
        
        # Connect signals
        self.send_btn.clicked.connect(self.send_message)
        self.input_field.returnPressed.connect(self.send_message)
    
    def add_message(self, text: str, is_user: bool = False, is_pending: bool = False) -> ChatBubble:
        """Add a message bubble to the chat."""
        bubble = ChatBubble(text, is_user, is_pending)
        
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        
        if is_user:
            container_layout.addStretch()
            container_layout.addWidget(bubble, 3)
        else:
            container_layout.addWidget(bubble, 3)
            container_layout.addStretch()
        
        self.chat_layout.addWidget(container)
        self.scroll_to_bottom()
        
        return bubble
    
    def scroll_to_bottom(self):
        """Scroll chat to bottom."""
        QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        ))
    
    def send_message(self):
        """Handle message sending."""
        text = self.input_field.text().strip()
        if not text:
            return
        
        # Add user message
        self.add_message(text, is_user=True)
        self.input_field.clear()
        
        # Disable input while processing
        self.input_field.setEnabled(False)
        self.send_btn.setEnabled(False)
        
        # Update HUD state
        self.state_changed.emit("THINKING")
        
        # Add pending message
        pending = self.add_message("thinking...", is_pending=True)
        
        # Process in background thread
        threading.Thread(
            target=self._process_message,
            args=(text, pending),
            daemon=True
        ).start()
    
    def _process_message(self, message: str, pending_bubble: ChatBubble):
        """Process message with orchestrator in background thread."""
        try:
            if ORCHESTRATOR_AVAILABLE:
                # Update state
                self.state_changed.emit("PROCESSING")
                
                result = orchestrator_handle_message(
                    message,
                    history=self.conversation_history,
                    session_id=self.session_id
                )
                reply = result.get("reply", "I couldn't process that.")
                cards = result.get("cards", [])
                
                # Update conversation history
                self.conversation_history.append({"role": "user", "content": message})
                self.conversation_history.append({"role": "assistant", "content": reply})
            else:
                reply = "Orchestrator not available. Please check your configuration."
                cards = []
            
            # Update UI on main thread
            QTimer.singleShot(0, lambda: self._show_reply(reply, cards, pending_bubble))
            
        except Exception as e:
            QTimer.singleShot(0, lambda: self._show_error(str(e), pending_bubble))
    
    def _show_reply(self, reply: str, cards: list, pending_bubble: ChatBubble):
        """Show reply and remove pending bubble."""
        # Remove pending bubble
        pending_bubble.parent().deleteLater()
        
        # Add reply
        self.add_message(reply)
        
        # Update HUD state back to listening
        self.state_changed.emit("LISTENING")
        
        # Handle news cards if any
        if cards:
            self._show_news_cards(cards)
        
        # Re-enable input
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_field.setFocus()
    
    def _show_error(self, error: str, pending_bubble: ChatBubble):
        """Show error message."""
        pending_bubble.parent().deleteLater()
        self.add_message(f"Error: {error}")
        
        self.state_changed.emit("IDLE")
        
        self.input_field.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input_field.setFocus()
    
    def _show_news_cards(self, cards: list):
        """Show news cards as separate windows."""
        for i, card in enumerate(cards[:5]):
            QTimer.singleShot(i * 300, lambda c=card: self._open_card(c))
    
    def _open_card(self, card: dict):
        """Open a single news card window."""
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            
            card_window = QMainWindow(self)
            card_window.setWindowTitle(card.get("source", "JARVIS News"))
            card_window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            card_window.setWindowFlags(
                Qt.WindowType.FramelessWindowHint |
                Qt.WindowType.WindowStaysOnTopHint
            )
            
            screen = QApplication.primaryScreen().geometry()
            x = screen.x() + 100 + (len(card_window.findChildren(QMainWindow)) * 40)
            y = screen.y() + 100
            
            card_window.setGeometry(x, y, 340, 260)
            
            web_view = QWebEngineView()
            web_view.setHtml(self._generate_card_html(card))
            card_window.setCentralWidget(web_view)
            
            card_window.show()
            
        except ImportError:
            print("PyQt6-WebEngine not available for news cards")
    
    def _generate_card_html(self, card: dict) -> str:
        """Generate HTML for news card."""
        title = card.get("title", "Untitled")
        source = card.get("source", "")
        body = card.get("body", "")
        url = card.get("url", "#")
        image = card.get("image", "")
        
        image_html = f'<img src="{image}" style="width:100%;height:120px;object-fit:cover;"/>' if image else ""
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap');
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'Orbitron', sans-serif;
                    background: rgba(5, 10, 15, 0.95);
                    border: 1px solid rgba(0, 255, 255, 0.6);
                    border-radius: 12px;
                    color: #eaf9ff;
                    overflow: hidden;
                }}
                .source {{
                    font-size: 9px;
                    letter-spacing: 2px;
                    color: #4fd6ff;
                    padding: 10px;
                }}
                .title {{
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0 10px;
                    color: #eaf9ff;
                }}
                .body {{
                    font-size: 11px;
                    padding: 10px;
                    color: #9fd3e8;
                    font-family: 'Courier New', monospace;
                }}
                .open {{
                    display: inline-block;
                    margin: 10px;
                    padding: 8px 16px;
                    background: linear-gradient(135deg, #4fd6ff, #00ffff);
                    color: #0a1620;
                    border-radius: 20px;
                    text-decoration: none;
                    font-size: 10px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            {image_html}
            <div class="source">{source}</div>
            <div class="title">{title}</div>
            <div class="body">{body}</div>
            <a class="open" href="{url}" target="_blank">Open Source</a>
        </body>
        </html>
        """


# ─── Main Window ────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    """Main JARVIS window with HUD Canvas and Chat integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S — MARK XLIX")
        self.setMinimumSize(900, 600)
        self.resize(1100, 750)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - 1100) // 2,
            (screen.height() - 750) // 2
        )
        
        self.setStyleSheet(f"background: {C.BG};")
        
        self.init_ui()
        
        # Clock timer
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Title bar
        main_layout.addWidget(self._create_title_bar())
        
        # Content area with HUD and Chat
        content_splitter = QSplitter(Qt.Orientation.Vertical)
        content_splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background: {C.BORDER};
                height: 3px;
            }}
        """)
        
        # HUD Canvas (top)
        self.hud = HudCanvas()
        self.hud.setMinimumHeight(250)
        content_splitter.addWidget(self.hud)
        
        # Chat area (bottom)
        self.chat = ChatWidget()
        self.chat.setMinimumHeight(200)
        content_splitter.addWidget(self.chat)
        
        # Connect chat state changes to HUD
        self.chat.state_changed.connect(self._update_hud_state)
        
        content_splitter.setSizes([400, 300])
        
        main_layout.addWidget(content_splitter)
        
        # Status bar
        main_layout.addWidget(self._create_status_bar())
    
    def _create_title_bar(self) -> QWidget:
        """Create custom title bar."""
        bar = QWidget()
        bar.setFixedHeight(50)
        bar.setStyleSheet(f"""
            background: {C.DARK};
            border-bottom: 1px solid {C.BORDER_B};
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        
        # Title
        title = QLabel("J.A.R.V.I.S")
        title.setFont(QFont("Courier New", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QLabel("MARK XLIX")
        subtitle.setFont(QFont("Courier New", 9))
        subtitle.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        layout.addWidget(subtitle)
        
        layout.addStretch()
        
        # Clock
        self._clock_label = QLabel()
        self._clock_label.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
        self._clock_label.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        layout.addWidget(self._clock_label)
        
        # Window controls
        for text, color in [("—", C.PRI_DIM), ("□", C.PRI), ("×", C.RED)]:
            btn = QPushButton(text)
            btn.setFixedSize(30, 30)
            btn.setFont(QFont("Courier New", 12, QFont.Weight.Bold))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {color};
                    border: 1px solid {C.BORDER};
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background: rgba(255, 255, 255, 0.05);
                }}
            """)
            
            if text == "—":
                btn.clicked.connect(self.showMinimized)
            elif text == "□":
                btn.clicked.connect(self.toggle_maximize)
            else:
                btn.clicked.connect(self.close)
            
            layout.addWidget(btn)
        
        return bar
    
    def _create_status_bar(self) -> QWidget:
        """Create bottom status bar."""
        bar = QWidget()
        bar.setFixedHeight(24)
        bar.setStyleSheet(f"""
            background: {C.DARK};
            border-top: 1px solid {C.BORDER};
        """)
        
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        
        self._status_label = QLabel("● SYSTEM READY")
        self._status_label.setFont(QFont("Courier New", 8))
        self._status_label.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        layout.addWidget(self._status_label)
        
        layout.addStretch()
        
        version = QLabel("v2.0 — Mark-L UI")
        version.setFont(QFont("Courier New", 8))
        version.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        layout.addWidget(version)
        
        return bar
    
    def _update_clock(self):
        """Update clock display."""
        self._clock_label.setText(time.strftime("%H:%M:%S"))
    
    def _update_hud_state(self, state: str):
        """Update HUD state from chat."""
        self.hud.state = state
        self.hud.speaking = (state == "SPEAKING")
        
        # Update status bar
        status_map = {
            "THINKING": ("◈  THINKING...", C.ACC2),
            "PROCESSING": ("▷  PROCESSING...", C.ACC2),
            "LISTENING": ("●  LISTENING", C.GREEN),
            "SPEAKING": ("●  SPEAKING", C.ACC),
            "IDLE": ("●  SYSTEM READY", C.GREEN),
        }
        text, color = status_map.get(state, ("●  SYSTEM READY", C.GREEN))
        self._status_label.setText(text)
        self._status_label.setStyleSheet(f"color: {color}; background: transparent;")
    
    def toggle_maximize(self):
        """Toggle maximized state."""
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Set dark palette
    palette = app.palette()
    palette.setColor(app.palette().ColorRole.Window, QColor(C.BG))
    palette.setColor(app.palette().ColorRole.WindowText, QColor(C.WHITE))
    palette.setColor(app.palette().ColorRole.Base, QColor(C.PANEL))
    palette.setColor(app.palette().ColorRole.Text, QColor(C.WHITE))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()