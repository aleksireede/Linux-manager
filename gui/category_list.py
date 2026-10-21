from PyQt5.QtCore import Qt, QSize, QTimer, QEvent
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QListWidgetItem, QPushButton, QSizePolicy, QStyle, QToolButton, QWidget


class _CategoryHeader(QWidget):
    def __init__(self, list_widget, item, label, category, toggle):
        super().__init__(list_widget)
        self.setObjectName("categoryHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._list_widget = list_widget
        self._item = item
        self._label = label
        self._category = category
        self._toggle = toggle
        self._label.installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self._label and event.type() == QEvent.MouseButtonRelease \
                and event.button() == Qt.LeftButton:
            self._toggle(self._category)
            return True
        return super().eventFilter(watched, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle(self._category)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self._update_item_height)

    def _update_item_height(self):
        self.layout().activate()
        label_height = self._label.heightForWidth(self._label.width())
        label_height += self._label.contentsMargins().top() + self._label.contentsMargins().bottom()
        height = max(label_height, 28) + self.layout().contentsMargins().top() + self.layout().contentsMargins().bottom()
        if self._item.sizeHint().height() != height:
            self._item.setSizeHint(QSize(0, height))
            self.setMinimumHeight(height)


def add_category_header(list_widget, category, collapsed, toggle, select_all=None):
    item = QListWidgetItem(category)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable & ~Qt.ItemFlag.ItemIsUserCheckable)
    list_widget.addItem(item)

    label = QLabel(category)
    label.setObjectName("categoryHeaderLabel")
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    header = _CategoryHeader(list_widget, item, label, category, toggle)
    layout = QHBoxLayout(header)
    layout.setContentsMargins(4, 0, 4, 0)
    arrow = QToolButton(header)
    arrow.setAutoRaise(True)
    arrow.setFixedSize(24, 28)
    arrow.setIcon(header.style().standardIcon(
        QStyle.SP_ArrowRight if collapsed else QStyle.SP_ArrowDown
    ))
    arrow.clicked.connect(lambda _checked=False, value=category: toggle(value))
    layout.addWidget(arrow)
    layout.addWidget(label, 1)
    if select_all:
        select_button = QPushButton("Select all", header)
        select_button.setObjectName("categorySelectAll")
        select_button.setFixedSize(82, 28)
        select_button.setToolTip(f"Select or clear all apps in {category}")
        select_button.clicked.connect(lambda _checked=False, value=category: select_all(value))
        layout.addWidget(select_button)
    item.setSizeHint(QSize(0, header.sizeHint().height()))
    list_widget.setItemWidget(item, header)
    return item
