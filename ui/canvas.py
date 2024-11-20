from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QPen, QColor, QImage, QPolygon, QPainterPath, QPolygonF
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent, pyqtSignal


class Canvas(QWidget):
    status_message = pyqtSignal(str)  # Define a signal for status messages

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(800, 600)  # Canvas size
        self.setAttribute(Qt.WA_StaticContents)

        self.image = QImage(self.size(), QImage.Format_RGB32)
        self.image.fill(Qt.white)  # Start with a white canvas
        self.original_image = self.image.copy()  # Preserve the original image

        self.current_scale = 1.0  # Keep track of zoom level
        self.offset_x = 0  # Track x-offset for centering
        self.offset_y = 0  # Track y-offset for centering

        self.tool = None  # Current tool ('rect', 'lasso', 'polygon')
        self.selection_start = None  # Starting point for selection
        self.selection_path = []  # Path for free-form or polygon selection
        self.drawing_selection = False
        self.selected_area = None  # Store the selected area as a QImage
        self.is_moving_selection = False  # Flag for moving selection
        self.selection_offset = QPoint()  # Offset during selection movement

        # Drawing variables
        self.drawing = False
        self.last_point = QPoint()
        self.brush_color = Qt.black
        self.brush_size = 3
        self.eraser_size = 10  # Default eraser size

        self.grabGesture(Qt.PinchGesture)

    def update_canvas_scale(self):
        """Update the canvas scale and redraw the image."""
        self.image = self.original_image.scaled(
            int(self.original_image.width() * self.current_scale),
            int(self.original_image.height() * self.current_scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.update()

    def set_eraser_size(self, size):
        """Set the eraser size."""
        self.eraser_size = size
        self.update()  # Update the canvas to reflect any changes if necessary

    def set_tool(self, tool):
        """Set the active tool (None for drawing, 'rect', 'lasso', 'polygon' for selection)."""
        self.tool = tool
        self.selection_start = None
        self.selection_path = []
        self.drawing_selection = False
        self.selected_area = None
        self.update()

    def copy_selection(self):
        """Copy the selected area to the clipboard."""
        if not self.selection_path:
            self.status_message.emit("No selection to copy.")
            return

        # Extract the selected area
        self.extract_selection()

        if self.selected_area:
            clipboard = QApplication.clipboard()
            clipboard.setImage(self.selected_area)
            self.status_message.emit("Selection copied to clipboard.")

    def paste_selection(self, position=None):
        """Paste clipboard image onto the canvas."""
        clipboard = QApplication.clipboard()
        clipboard_image = clipboard.image()

        if clipboard_image.isNull():
            self.status_message.emit("Clipboard is empty.")
            return

        paste_position = position or QPoint(0, 0)
        painter = QPainter(self.original_image)
        painter.drawImage(paste_position, clipboard_image)
        painter.end()

        self.image = self.original_image.scaled(
            int(self.original_image.width() * self.current_scale),
            int(self.original_image.height() * self.current_scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

        # Create rectangular selection for pasted image
        self.selection_start = paste_position
        self.selection_path = [
            paste_position,
            paste_position + QPoint(clipboard_image.width(), clipboard_image.height()),
        ]
        self.selected_area = clipboard_image

        self.update()
        self.status_message.emit("Image pasted with selection.")

    def set_brush_color(self, color):
        """Set the brush color."""
        self.brush_color = QColor(color)
        self.update()  # Update the canvas to reflect any changes if necessary

    # Test test test
    def draw_rectangle(self, rect: QRect, color: str):
        painter = QPainter(self)
        pen = QPen(color)
        painter.setPen(pen)
        painter.drawRect(rect)
        self.update()

    def draw_triangle(self, points: QPolygon, color: str):
        painter = QPainter(self)
        pen = QPen(color)
        painter.setPen(pen)
        painter.drawPolygon(points)
        self.update()

    def draw_circle(self, center: QPoint, radius: int, color: str):
        painter = QPainter(self)
        pen = QPen(color)
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius)
        self.update()

    def draw_line(self, start: QPoint, end: QPoint, color: str):
        painter = QPainter(self)
        pen = QPen(color)
        painter.setPen(pen)
        painter.drawLine(start, end)
        self.update()

    def set_brush_size(self, size):
        """Set the brush size."""
        self.brush_size = size
        self.update()  # Update the canvas to reflect any changes if necessary

    def paintEvent(self, event):
        """Render the image and selection on the canvas."""
        canvas_painter = QPainter(self)

        # Adjust for centering
        self.offset_x = max((self.width() - self.image.width()) // 2, 0)
        self.offset_y = max((self.height() - self.image.height()) // 2, 0)

        # Draw the image
        canvas_painter.drawImage(self.offset_x, self.offset_y, self.image)

        # Draw the selection overlay
        if self.selection_path:
            pen = QPen(Qt.blue, 2, Qt.DashLine)
            canvas_painter.setPen(pen)
            scaled_path = [self.map_from_scaled_image(point) for point in self.selection_path]

            if self.tool == 'rect' and len(self.selection_path) == 2:
                rect = QRect(scaled_path[0], scaled_path[1])
                canvas_painter.drawRect(rect)
            elif self.tool in ['lasso', 'polygon']:
                poly = QPolygon(scaled_path)
                canvas_painter.drawPolyline(poly)

    def clear_canvas(self):
        """Clear the canvas to a blank state."""
        self.image.fill(Qt.white)
        self.original_image = self.image.copy()  # Reset the original image
        self.selected_area = None  # Clear any selected area
        self.selection_start = None
        self.selection_path = []
        self.drawing_selection = False
        self.is_moving_selection = False
        self.update()

    def finalize_selection(self):
        """Finalize the selection without scaling issues."""
        if self.selection_path:
            self.selection_path = [
                self.map_to_scaled_image(point) for point in self.selection_path
            ]
            self.extract_selection()
        self.update()

    def mousePressEvent(self, event):
        """Handle mouse press for both drawing and selection tools."""
        pos = self.map_to_scaled_image(event.pos())  # Use map_to_scaled_image instead

        if pos.x() != -1 and pos.y() != -1:
            if self.selected_area and self.get_selection_rect().contains(pos):
                # Start moving the selection
                self.is_moving_selection = True
                self.selection_offset = pos - self.selection_start
            else:
                # Clear selection if clicked outside
                self.is_moving_selection = False
                self.selection_start = None
                self.selection_path = []
                self.selected_area = None

            if self.tool == 'rect':
                self.selection_start = pos
                self.selection_path = [pos]
            elif self.tool in ['lasso', 'polygon']:
                if not self.drawing_selection:
                    self.selection_path = [pos]
                self.drawing_selection = True
            elif self.tool is None and event.button() == Qt.LeftButton:
                self.drawing = True
                self.last_point = pos
            elif self.tool == 'erase':
                self.drawing = True
                self.last_point = pos

            self.update()

    def mouseMoveEvent(self, event):
        """Handle mouse move for selection tools and drawing."""
        pos = self.map_to_scaled_image(event.pos())  # Use map_to_scaled_image instead

        if self.is_moving_selection and self.selected_area:
            # Move the selection
            self.selection_start = pos - self.selection_offset
            self.update()
        elif self.tool == 'rect' and self.selection_start:
            self.selection_path = [self.selection_start, pos]
            self.update()
        elif self.tool in ['lasso', 'polygon'] and self.drawing_selection:
            self.selection_path.append(pos)
            self.update()
        elif self.tool is None and self.drawing:
            # Drawing
            painter = QPainter(self.original_image)
            pen = QPen(self.brush_color, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.last_point, pos)
            self.last_point = pos
            self.image = self.original_image.scaled(
                int(self.original_image.width() * self.current_scale),
                int(self.original_image.height() * self.current_scale),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.update()
        elif self.tool == 'erase' and self.drawing:
            painter = QPainter(self.original_image)
            pen = QPen(Qt.white, self.eraser_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(self.last_point, pos)
            self.last_point = pos
            self.image = self.original_image.scaled(
                int(self.original_image.width() * self.current_scale),
                int(self.original_image.height() * self.current_scale),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release for selection tools."""
        if self.is_moving_selection:
            self.is_moving_selection = False
        elif self.tool in ['rect', 'lasso', 'polygon']:
            self.drawing_selection = False
            self.finalize_selection()
        elif self.tool == 'erase' or self.tool is None:
            self.drawing = False
        self.update()

    def cut_selection(self):
        """Cut and clear the selected area, replacing it with white."""
        if not self.selection_path:
            self.status_message.emit("No selection to cut.")
            return

        self.copy_selection()  # Copy selected area

        painter = QPainter(self.original_image)

        if self.tool == 'rect' and len(self.selection_path) == 2:
            rect = self.get_selection_rect()
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(rect, Qt.white)  # Fill with white
        elif self.tool in ['lasso', 'polygon']:
            mask = QImage(self.original_image.size(), QImage.Format_ARGB32)
            mask.fill(Qt.transparent)
            mask_painter = QPainter(mask)
            path = QPainterPath()
            path.addPolygon(QPolygonF(self.selection_path))
            mask_painter.fillPath(path, Qt.white)  # Fill selection with white
            mask_painter.end()
            painter.drawImage(0, 0, mask)

        painter.end()

        # Re-scale the image to match the current scale and update
        self.image = self.original_image.scaled(
            int(self.original_image.width() * self.current_scale),
            int(self.original_image.height() * self.current_scale),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.update()
        self.selection_path = []
        self.selected_area = None
        self.status_message.emit("Selection cut.")

    def extract_selection(self):
        """Extract the selected area as a QImage."""
        if not self.selection_path:
            self.status_message.emit("No selection to extract.")
            return

        # Handle lasso/polygon selection
        if self.tool in ['lasso', 'polygon']:
            mask = QImage(self.original_image.size(), QImage.Format_ARGB32)
            mask.fill(Qt.transparent)
            painter = QPainter(mask)
            path = QPainterPath()
            path.addPolygon(QPolygonF(self.selection_path))
            painter.fillPath(path, Qt.white)
            painter.end()

            self.selected_area = QImage(self.original_image.size(), QImage.Format_ARGB32)
            self.selected_area.fill(Qt.transparent)
            painter = QPainter(self.selected_area)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.drawImage(0, 0, self.original_image)
            painter.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            painter.drawImage(0, 0, mask)
            painter.end()

        # Handle rectangular selection
        elif self.tool == 'rect' and self.selection_start:
            rect = self.get_selection_rect()
            if rect.isValid():
                self.selected_area = self.original_image.copy(rect)

        self.status_message.emit("Selection extracted.")

    def get_selection_rect(self):
        """Calculate the rectangular selection area."""
        if not self.selection_start or not self.selection_path:
            return QRect()
        start = self.selection_start
        end = self.selection_path[-1]
        x1, y1 = min(start.x(), end.x()), min(start.y(), end.y())
        x2, y2 = max(start.x(), end.x()), max(start.y(), end.y())
        return QRect(x1, y1, x2 - x1, y2 - y1)

    #def map_to_image(self, pos):
    #    """Map the cursor position on the widget to the corresponding position on the image."""
    #    # Adjust for the offsets and scale
    #    x = (pos.x() - self.offset_x) / self.current_scale
    #    y = (pos.y() - self.offset_y) / self.current_scale
    #
    #    # Ensure the coordinates are within the image bounds
    #    if 0 <= x < self.original_image.width() and 0 <= y < self.original_image.height():
    #        return QPoint(int(x), int(y))
    #    return QPoint(-1, -1)

    def map_to_scaled_image(self, pos):
        """Map widget coordinates to the scaled image coordinates."""
        x = (pos.x() - self.offset_x) / self.current_scale
        y = (pos.y() - self.offset_y) / self.current_scale
        return QPoint(int(x), int(y))

    def map_from_scaled_image(self, pos):
        """Map scaled image coordinates back to widget coordinates."""
        x = int(pos.x() * self.current_scale + self.offset_x)
        y = int(pos.y() * self.current_scale + self.offset_y)
        return QPoint(x, y)

    def event(self, event):
        """Handle gestures."""
        if event.type() == QEvent.Gesture:
            return self.gestureEvent(event)
        return super().event(event)

    def gestureEvent(self, event):
        """Handle gestures like pinch zoom."""
        gesture = event.gesture(Qt.PinchGesture)
        if gesture:
            self.handle_pinch(gesture)
            return True
        return super().event(event)

    def handle_pinch(self, gesture):
        """Zoom in or out based on pinch gesture."""
        if self.original_image.isNull():
            return

        if gesture.state() in (Qt.GestureStarted, Qt.GestureUpdated):
            scale_factor = gesture.scaleFactor()
            new_scale = self.current_scale * scale_factor

            # Enforce scaling limits
            new_scale = max(0.1, min(5.0, new_scale))  # Zoom range: 0.1x to 5.0x

            if new_scale != self.current_scale:
                self.current_scale = new_scale
                self.image = self.original_image.scaled(
                    int(self.original_image.width() * self.current_scale),
                    int(self.original_image.height() * self.current_scale),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.update()

