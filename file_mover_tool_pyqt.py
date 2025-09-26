import sys
import os
import shutil
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QFrame, QMessageBox,
    QProgressBar, QRadioButton, QButtonGroup, QFileDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt5.QtGui import QDragEnterEvent, QDropEvent

class DragDropLineEdit(QLineEdit):
    """支持拖拽的输入框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 2px solid #ccc;
                border-radius: 4px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QLineEdit:hover {
                border-color: #888;
            }
        """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self.styleSheet() + "QLineEdit { background-color: #e6f3ff; }")
    
    def dragLeaveEvent(self, event):
        self.setStyleSheet(self.styleSheet().replace("QLineEdit { background-color: #e6f3ff; }", ""))
    
    def dropEvent(self, event: QDropEvent):
        self.setStyleSheet(self.styleSheet().replace("QLineEdit { background-color: #e6f3ff; }", ""))
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if os.path.isdir(file_path):
                self.setText(file_path)
                event.acceptProposedAction()
            else:
                QMessageBox.warning(self, "警告", "请拖拽文件夹，不是文件")

class MappingRow(QFrame):
    """映射行组件"""
    def __init__(self, parent=None, on_delete=None, group_number=1):
        super().__init__(parent)
        self.on_delete = on_delete
        self.group_number = group_number
        self.setup_ui()
        
    def setup_ui(self):
        self.setFrameStyle(QFrame.Box)
        self.setStyleSheet("QFrame { margin: 2px; padding: 5px; }")
        
        layout = QHBoxLayout()
        
        # 编号标签
        self.group_label = QLabel(f"第{self.group_number}组")
        self.group_label.setStyleSheet("""
            QLabel {
                font-size: 12pt;
                font-weight: bold;
                color: #0078d4;
                background-color: #e6f3ff;
                padding: 10px;
                border-radius: 4px;
                min-width: 60px;
            }
        """)
        self.group_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.group_label)
        
        # 源文件夹
        source_layout = QVBoxLayout()
        source_layout.addWidget(QLabel("源文件夹:"))
        self.source_edit = DragDropLineEdit()
        source_layout.addWidget(self.source_edit)
        
        source_btn = QPushButton("浏览")
        source_btn.clicked.connect(lambda: self.browse_folder(self.source_edit))
        source_layout.addWidget(source_btn)
        
        layout.addLayout(source_layout)
        
        # 箭头
        arrow_label = QLabel("→")
        arrow_label.setStyleSheet("font-size: 20pt; font-weight: bold; color: #0078d4;")
        arrow_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(arrow_label)
        
        # 目标文件夹
        target_layout = QVBoxLayout()
        target_layout.addWidget(QLabel("目标文件夹:"))
        self.target_edit = DragDropLineEdit()
        target_layout.addWidget(self.target_edit)
        
        target_btn = QPushButton("浏览")
        target_btn.clicked.connect(lambda: self.browse_folder(self.target_edit))
        target_layout.addWidget(target_btn)
        
        layout.addLayout(target_layout)
        
        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; }")
        delete_btn.clicked.connect(self.delete_row)
        layout.addWidget(delete_btn)
        
        self.setLayout(layout)
    
    def browse_folder(self, line_edit):
        """浏览选择文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if folder:
            line_edit.setText(folder)
    
    def delete_row(self):
        """删除当前行"""
        if self.on_delete:
            self.on_delete(self)
    
    def get_mapping(self):
        """获取映射配置"""
        source = self.source_edit.text().strip()
        target = self.target_edit.text().strip()
        return (source, target) if source and target else None

class FileOperationThread(QThread):
    """文件操作线程"""
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished = pyqtSignal(bool, str)
    
    def __init__(self, mappings, operation):
        super().__init__()
        self.mappings = mappings
        self.operation = operation
    
    def run(self):
        try:
            total_files = 0
            processed_files = 0
            
            # 计算总文件数
            for source, _ in self.mappings:
                if os.path.exists(source):
                    for _, _, files in os.walk(source):
                        total_files += len(files)
            
            if total_files == 0:
                self.finished.emit(False, "没有找到任何文件")
                return
            
            # 执行操作
            for source, target in self.mappings:
                if not os.path.exists(source):
                    continue
                
                # 创建目标文件夹
                os.makedirs(target, exist_ok=True)
                
                # 处理文件
                for root_dir, dirs, files in os.walk(source):
                    # 计算相对路径
                    rel_path = os.path.relpath(root_dir, source)
                    target_dir = os.path.join(target, rel_path) if rel_path != '.' else target
                    
                    # 创建目标子目录
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # 处理文件
                    for file in files:
                        source_file = os.path.join(root_dir, file)
                        target_file = os.path.join(target_dir, file)
                        
                        try:
                            if self.operation == "move":
                                shutil.move(source_file, target_file)
                            else:  # copy
                                shutil.copy2(source_file, target_file)
                            
                            processed_files += 1
                            progress = int((processed_files / total_files) * 100)
                            self.progress_updated.emit(progress)
                            self.status_updated.emit(f"正在处理: {file} ({processed_files}/{total_files})")
                            
                        except Exception as e:
                            self.finished.emit(False, f"处理文件 {file} 失败: {str(e)}")
                            return
            
            self.finished.emit(True, f"成功{self.operation == 'move' and '移动' or '复制'} {processed_files} 个文件")
            
        except Exception as e:
            self.finished.emit(False, f"操作失败: {str(e)}")

class FileMoverToolPyQt(QMainWindow):
    """PyQt版本的文件移动工具"""
    def __init__(self):
        super().__init__()
        self.mapping_rows = []
        self.operation_thread = None
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("文件移动工具 (PyQt版本)")
        self.setGeometry(100, 100, 1000, 700)
        
        # 设置样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                font-size: 10pt;
                color: #333;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                background-color: #0078d4;
                color: white;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # 标题
        title_label = QLabel("文件移动工具 (PyQt版本)")
        title_label.setStyleSheet("font-size: 18pt; font-weight: bold; color: #0078d4; margin: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 操作模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("操作模式:"))
        
        self.mode_group = QButtonGroup()
        self.copy_radio = QRadioButton("复制模式")
        self.move_radio = QRadioButton("移动模式")
        self.copy_radio.setChecked(True)
        
        self.mode_group.addButton(self.copy_radio)
        self.mode_group.addButton(self.move_radio)
        
        mode_layout.addWidget(self.copy_radio)
        mode_layout.addWidget(self.move_radio)
        mode_layout.addStretch()
        
        main_layout.addLayout(mode_layout)
        
        # 映射区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: 1px solid #ccc; background-color: white; }")
        
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        self.scroll_widget.setLayout(self.scroll_layout)
        scroll_area.setWidget(self.scroll_widget)
        
        main_layout.addWidget(scroll_area)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        add_btn = QPushButton("添加映射")
        add_btn.clicked.connect(self.add_mapping_row)
        button_layout.addWidget(add_btn)
        
        clear_btn = QPushButton("清空所有")
        clear_btn.setStyleSheet("QPushButton { background-color: #d32f2f; }")
        clear_btn.clicked.connect(self.clear_all_mappings)
        button_layout.addWidget(clear_btn)
        
        button_layout.addStretch()
        
        self.execute_btn = QPushButton("开始执行")
        self.execute_btn.setStyleSheet("QPushButton { background-color: #2e7d32; font-size: 12pt; }")
        self.execute_btn.clicked.connect(self.execute_operation)
        button_layout.addWidget(self.execute_btn)
        
        main_layout.addLayout(button_layout)
        
        # 状态栏
        self.status_label = QLabel("就绪 - 支持拖拽功能")
        self.status_label.setStyleSheet("padding: 5px; background-color: #e8f5e8; border: 1px solid #4caf50;")
        main_layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 添加第一个映射行
        self.add_mapping_row()
    
    def add_mapping_row(self):
        """添加映射行"""
        group_number = len(self.mapping_rows) + 1
        row = MappingRow(on_delete=self.remove_mapping_row, group_number=group_number)
        self.mapping_rows.append(row)
        self.scroll_layout.addWidget(row)
        self.update_group_numbers()
    
    def remove_mapping_row(self, row):
        """删除映射行"""
        if len(self.mapping_rows) > 1:  # 至少保留一行
            self.mapping_rows.remove(row)
            row.deleteLater()
            self.update_group_numbers()
        else:
            QMessageBox.information(self, "提示", "至少需要保留一个映射行")
    
    def clear_all_mappings(self):
        """清空所有映射"""
        reply = QMessageBox.question(self, "确认", "确定要清空所有映射吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            for row in self.mapping_rows[:]:
                row.deleteLater()
            self.mapping_rows.clear()
            self.add_mapping_row()
    
    def update_group_numbers(self):
        """更新所有映射行的编号"""
        for i, row in enumerate(self.mapping_rows, 1):
            row.group_number = i
            row.group_label.setText(f"第{i}组")
    
    def validate_mappings(self):
        """验证映射配置"""
        valid_mappings = []
        
        for row in self.mapping_rows:
            mapping = row.get_mapping()
            if mapping:
                source, target = mapping
                
                if not os.path.exists(source):
                    QMessageBox.critical(self, "错误", f"源文件夹不存在: {source}")
                    return None
                
                if not os.path.isdir(source):
                    QMessageBox.critical(self, "错误", f"源路径不是文件夹: {source}")
                    return None
                
                if source == target:
                    QMessageBox.critical(self, "错误", "源文件夹和目标文件夹不能相同")
                    return None
                
                valid_mappings.append((source, target))
        
        if not valid_mappings:
            QMessageBox.warning(self, "警告", "请至少添加一个有效的映射")
            return None
        
        return valid_mappings
    
    def execute_operation(self):
        """执行文件操作"""
        mappings = self.validate_mappings()
        if not mappings:
            return
        
        operation = "copy" if self.copy_radio.isChecked() else "move"
        operation_text = "复制" if operation == "copy" else "移动"
        
        reply = QMessageBox.question(self, "确认执行",
                                   f"确定要{operation_text} {len(mappings)} 个文件夹的内容吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.start_operation(mappings, operation)
    
    def start_operation(self, mappings, operation):
        """开始文件操作"""
        self.execute_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.operation_thread = FileOperationThread(mappings, operation)
        self.operation_thread.progress_updated.connect(self.progress_bar.setValue)
        self.operation_thread.status_updated.connect(self.status_label.setText)
        self.operation_thread.finished.connect(self.operation_finished)
        self.operation_thread.start()
    
    def operation_finished(self, success, message):
        """操作完成处理"""
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        
        if success:
            self.status_label.setText("操作完成！")
            QMessageBox.information(self, "成功", message)
        else:
            self.status_label.setText("操作失败")
            QMessageBox.critical(self, "错误", message)
        
        self.operation_thread = None

def main():
    app = QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle('Fusion')
    
    window = FileMoverToolPyQt()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()