import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit, 
    QComboBox, QGroupBox, QFormLayout, QMainWindow,
    QSpinBox, QMessageBox, QDoubleSpinBox, QCheckBox, QFileDialog, QGridLayout
)
from PyQt6.QtCore import pyqtSignal, QObject
from core.manager import AutomationManager
from core.logger import AppLogger
from core.task_runner import TaskRunner
from api.hero_sms import HeroSMS

class LoggerSignaler(QObject):
    log_signal = pyqtSignal(str, str)

class GuiLogger(AppLogger):
    def __init__(self, signaler):
        super().__init__()
        self.signaler = signaler

    def info(self, msg, status="INFO"):
        msg = self._format_msg(msg)
        self.signaler.log_signal.emit(msg, status)
        print(f"[{status}] {msg}")

    def warning(self, msg, status="WARN"):
        msg = self._format_msg(msg)
        self.signaler.log_signal.emit(msg, status)
        print(f"[{status}] {msg}")

    def error(self, msg, status="ERROR"):
        msg = self._format_msg(msg)
        self.signaler.log_signal.emit(msg, status)
        print(f"[{status}] {msg}")

class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram 自动化注册与群控系统")
        self.resize(1000, 700)
        
        self.signaler = LoggerSignaler()
        self.signaler.log_signal.connect(self.append_log)
        
        self.logger = GuiLogger(self.signaler)
        self.manager = AutomationManager(self.logger)
        self.runner = None
        
        self._init_ui()
        self.refresh_instances()

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left Panel - Configs
        left_panel = QVBoxLayout()
        main_layout.addLayout(left_panel, 1)
        
        # 1. Emulator Control Group
        ld_group = QGroupBox("1. 雷电模拟器设置")
        ld_layout = QFormLayout()
        
        self.ld_path_input = QLineEdit(self.manager.config.get_ld_path())
        self.ld_path_input.textChanged.connect(lambda t: self.manager.config.set_ld_path(t))
        ld_path_btn = QPushButton("保存路径")
        ld_path_btn.setFixedWidth(ld_path_btn.sizeHint().width())
        ld_path_btn.clicked.connect(self.save_ld_path)
        
        ld_path_row = QHBoxLayout()
        ld_path_row.addWidget(self.ld_path_input)
        ld_path_row.addWidget(ld_path_btn)
        ld_layout.addRow("雷电路径:", ld_path_row)
        
        self.source_combo = QComboBox()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setFixedWidth(ld_path_btn.sizeHint().width())
        refresh_btn.clicked.connect(self.refresh_instances)
        
        src_row = QHBoxLayout()
        src_row.addWidget(self.source_combo)
        src_row.addWidget(refresh_btn)
        ld_layout.addRow("克隆源模拟器:", src_row)
        
        ld_group.setLayout(ld_layout)
        left_panel.addWidget(ld_group)
        
        # 2. Task Configuration Group
        task_group = QGroupBox("2. 注册任务设置")
        task_layout = QVBoxLayout()
        
        # Row 1
        row1_layout = QHBoxLayout()
        row1_layout.addWidget(QLabel("注册数量:"))
        self.target_count_input = QSpinBox()
        self.target_count_input.setRange(1, 10000)
        self.target_count_input.setValue(self.manager.config.get_target_count())
        self.target_count_input.valueChanged.connect(lambda v: self.manager.config.set_target_count(v))
        row1_layout.addWidget(self.target_count_input)
        
        row1_layout.addSpacing(20)
        
        row1_layout.addWidget(QLabel("同时任务数:"))
        self.concurrency_input = QSpinBox()
        self.concurrency_input.setRange(1, 50)
        self.concurrency_input.setValue(self.manager.config.get_concurrency())
        self.concurrency_input.valueChanged.connect(lambda v: self.manager.config.set_concurrency(v))
        row1_layout.addWidget(self.concurrency_input)
        
        row1_layout.addStretch()
        task_layout.addLayout(row1_layout)
        
        # Row 2
        row2_layout = QHBoxLayout()
        row2_layout.addWidget(QLabel("代理文件(txt):"))
        self.proxy_path_input = QLineEdit(self.manager.config.get_proxy_file())
        self.proxy_path_input.setReadOnly(True)
        # self.proxy_path_input.textChanged.connect(lambda t: self.manager.config.set_proxy_file(t))
        # proxy_btn = QPushButton("选择文件")
        # proxy_btn.clicked.connect(self.select_proxy_file)
        row2_layout.addWidget(self.proxy_path_input)
        # row2_layout.addWidget(proxy_btn)
        task_layout.addLayout(row2_layout)
        
        # Row 3
        row3_layout = QHBoxLayout()
        self.get_api_checkbox = QCheckBox("获取API")
        self.get_session_checkbox = QCheckBox("获取session")
        
        self.get_api_checkbox.setChecked(self.manager.config.config.get('get_api', False))
        self.get_session_checkbox.setChecked(self.manager.config.config.get('get_session', False))
        
        self.get_api_checkbox.stateChanged.connect(self._on_get_api_changed)
        self.get_session_checkbox.stateChanged.connect(self._on_get_session_changed)
        
        row3_layout.addWidget(self.get_api_checkbox)
        row3_layout.addWidget(self.get_session_checkbox)
        row3_layout.addStretch()
        task_layout.addLayout(row3_layout)
        
        # Row 4
        row4_layout = QHBoxLayout()
        row4_layout.addWidget(QLabel("API程序预设名称:"))
        self.api_app_preset_input = QLineEdit(self.manager.config.config.get('api_app_preset', ''))
        self.api_app_preset_input.textChanged.connect(self._on_api_preset_changed)
        api_preset_btn = QPushButton("选择文件")
        api_preset_btn.clicked.connect(self.select_api_preset_file)
        row4_layout.addWidget(self.api_app_preset_input)
        row4_layout.addWidget(api_preset_btn)
        task_layout.addLayout(row4_layout)
        
        task_group.setLayout(task_layout)
        left_panel.addWidget(task_group)
        
        # 3. SMS Configuration Group
        sms_group = QGroupBox("3. 接码平台 (Hero-SMS)")
        sms_layout = QGridLayout()
        
        # Row 1: API Key
        sms_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_input = QLineEdit(self.manager.config.get_hero_sms_api_key())
        self.api_key_input.textChanged.connect(lambda t: self.manager.config.set_hero_sms_api_key(t))
        sms_layout.addWidget(self.api_key_input, 0, 1, 1, 3)
        
        # Row 2: 注册平台 & 国家/any
        sms_layout.addWidget(QLabel("注册平台:"), 1, 0)
        self.platform_input = QLineEdit(self.manager.config.get_sms_service())
        self.platform_input.textChanged.connect(lambda t: self.manager.config.set_sms_service(t))
        sms_layout.addWidget(self.platform_input, 1, 1)
        
        sms_layout.addWidget(QLabel("国家/any:"), 1, 2)
        self.country_input = QLineEdit(self.manager.config.get_sms_country())
        self.country_input.textChanged.connect(lambda t: self.manager.config.set_sms_country(t))
        sms_layout.addWidget(self.country_input, 1, 3)
        
        # Row 3: 余额 & 最高价格
        sms_layout.addWidget(QLabel("余额:"), 2, 0)
        
        bal_layout = QHBoxLayout()
        self.balance_lbl = QLabel("Unknown")
        bal_layout.addWidget(self.balance_lbl)
        
        bal_btn = QPushButton("查询")
        bal_btn.setFixedWidth(60)
        bal_btn.clicked.connect(self.check_balance)
        bal_layout.addWidget(bal_btn)
        sms_layout.addLayout(bal_layout, 2, 1)
        
        sms_layout.addWidget(QLabel("最高价格($):"), 2, 2)
        self.price_input = QLineEdit(self.manager.config.get_sms_price())
        self.price_input.textChanged.connect(lambda t: self.manager.config.set_sms_price(t))
        sms_layout.addWidget(self.price_input, 2, 3)
        
        sms_group.setLayout(sms_layout)
        left_panel.addWidget(sms_group)

        # 4. Password and Email Group
        pwd_group = QGroupBox("4. 设置密码并绑定邮箱")
        pwd_layout = QFormLayout()
        
        self.enable_pwd_checkbox = QCheckBox("开启设置密码并绑定邮箱")
        self.enable_pwd_checkbox.setChecked(self.manager.config.get_enable_password_setup())
        self.enable_pwd_checkbox.stateChanged.connect(lambda state: self.manager.config.set_enable_password_setup(bool(state)))
        pwd_layout.addRow(self.enable_pwd_checkbox)
        
        self.email_path_input = QLineEdit(self.manager.config.get_email_file_path())
        self.email_path_input.setReadOnly(True)
        # email_btn = QPushButton("选择文件")
        # email_btn.clicked.connect(self.select_email_file)
        email_row = QHBoxLayout()
        email_row.addWidget(self.email_path_input)
        # email_row.addWidget(email_btn)
        pwd_layout.addRow("邮箱列表:", email_row)
        
        pwd_group.setLayout(pwd_layout)
        left_panel.addWidget(pwd_group)

        # 5. File Save Paths Group
        save_group = QGroupBox("5. 文件保存路径")
        save_layout = QFormLayout()
        
        self.failed_video_input = QLineEdit(self.manager.config.get_failed_video_path())
        self.failed_video_input.setReadOnly(True)
        # failed_video_btn = QPushButton("选择文件夹")
        # failed_video_btn.clicked.connect(self.select_failed_video_dir)
        fv_row = QHBoxLayout()
        fv_row.addWidget(self.failed_video_input)
        # fv_row.addWidget(failed_video_btn)
        save_layout.addRow("注册失败视频:", fv_row)
        
        self.account_data_input = QLineEdit(self.manager.config.get_account_data_path())
        self.account_data_input.setReadOnly(True)
        # account_data_btn = QPushButton("选择文件夹")
        # account_data_btn.clicked.connect(self.select_account_data_dir)
        ad_row = QHBoxLayout()
        ad_row.addWidget(self.account_data_input)
        # ad_row.addWidget(account_data_btn)
        save_layout.addRow("账号资料:", ad_row)
        
        save_group.setLayout(save_layout)
        left_panel.addWidget(save_group)

        # Start / Stop Buttons
        action_layout = QHBoxLayout()
        self.start_btn = QPushButton("🚀 开始全自动注册")
        self.start_btn.setMinimumHeight(50)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self.start_task)
        
        self.stop_btn = QPushButton("🛑 停止任务")
        self.stop_btn.setMinimumHeight(50)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; font-size: 14px;")
        self.stop_btn.clicked.connect(self.stop_task)
        self.stop_btn.setEnabled(False)
        
        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.stop_btn)
        left_panel.addLayout(action_layout)
        left_panel.addStretch()
        
        # Right Panel - Logs
        right_panel = QVBoxLayout()
        main_layout.addLayout(right_panel, 2)
        
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas, monospace;")
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        right_panel.addWidget(log_group)

    def select_proxy_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择代理文件", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.proxy_path_input.setText(path)
            self.manager.config.set_proxy_file(path)

    def select_email_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择邮箱列表文件", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.email_path_input.setText(path)
            self.manager.config.set_email_file_path(path)

    def select_failed_video_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择保存注册失败视频的文件夹")
        if path:
            self.failed_video_input.setText(path)
            self.manager.config.set_failed_video_path(path)

    def select_account_data_dir(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择保存账号资料的文件夹")
        if path:
            self.account_data_input.setText(path)
            self.manager.config.set_account_data_path(path)

    def select_api_preset_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "选择API程序预设文件", "", "Text Files (*.txt);;All Files (*)")
        if path:
            self.api_app_preset_input.setText(path)
            self.manager.config.config['api_app_preset'] = path
            self.manager.config.save_config()

    def _on_api_preset_changed(self, text):
        self.manager.config.config['api_app_preset'] = text
        self.manager.config.save_config()

    def _on_get_api_changed(self, state):
        self.manager.config.config['get_api'] = bool(state)
        self.manager.config.save_config()
        if not bool(state) and self.get_session_checkbox.isChecked():
            self.get_session_checkbox.blockSignals(True)
            self.get_session_checkbox.setChecked(False)
            self.manager.config.config['get_session'] = False
            self.manager.config.save_config()
            self.get_session_checkbox.blockSignals(False)

    def _on_get_session_changed(self, state):
        self.manager.config.config['get_session'] = bool(state)
        self.manager.config.save_config()
        if bool(state) and not self.get_api_checkbox.isChecked():
            self.get_api_checkbox.blockSignals(True)
            self.get_api_checkbox.setChecked(True)
            self.manager.config.config['get_api'] = True
            self.manager.config.save_config()
            self.get_api_checkbox.blockSignals(False)

    def save_ld_path(self):
        path = self.ld_path_input.text()
        self.manager.set_ld_path(path)
        self.logger.info("雷电模拟器路径已保存", "配置")
        self.refresh_instances()
        
    def check_balance(self):
        api_key = self.api_key_input.text().strip()
        if not api_key:
            self.logger.warning("请输入 API Key", "接码平台")
            return
        sms = HeroSMS(api_key)
        bal = sms.get_balance()
        self.balance_lbl.setText(f"${bal}" if bal != "Unknown" else bal)
        self.logger.info(f"拉取到余额: {bal}", "接码平台")
        
    def refresh_instances(self):
        try:
            instances = self.manager.get_instances()
            self.source_combo.clear()
            for inst in instances:
                desc = f"[{inst['index']}] {inst['name']}"
                self.source_combo.addItem(desc, inst['index'])
        except Exception as e:
            self.logger.warning(f"刷新模拟器抛出异常, 可能是路径不对: {e}", "系统")
            
    def start_task(self):
        src_idx = self.source_combo.currentData()
        if src_idx is None:
            QMessageBox.warning(self, "错误", "缺少克隆源模拟器！")
            return
            
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "错误", "请配置 Hero-SMS API Key！")
            return
            
        self.manager.config.set_hero_sms_api_key(api_key)
        self.manager.config.set_target_count(self.target_count_input.value())
        self.manager.config.set_concurrency(self.concurrency_input.value())
        self.manager.config.set_sms_service(self.platform_input.text().strip())
        self.manager.config.set_sms_country(self.country_input.text().strip())
        self.manager.config.set_sms_price(self.price_input.text().strip())
        # self.manager.config.set_proxy_file(self.proxy_path_input.text().strip())
        
        config = {
            'source_index': src_idx,
            'target_count': self.target_count_input.value(),
            'concurrency': self.concurrency_input.value(),
            'api_key': api_key,
            'service': self.platform_input.text().strip(),
            'country': self.country_input.text().strip(),
            'max_price': self.price_input.text().strip(),
            'proxy_file': self.manager.config.get_proxy_file(),
            'get_api': self.get_api_checkbox.isChecked(),
            'get_session': self.get_session_checkbox.isChecked(),
            'api_app_preset': self.api_app_preset_input.text().strip(),
            'enable_password_setup': self.enable_pwd_checkbox.isChecked(),
            'email_file_path': self.manager.config.get_email_file_path(),
            'save_data_path': self.manager.config.get_account_data_path(),
            'prefix': 'TGClone_'
        }
        
        self.runner = TaskRunner(self.manager, self.logger, config)
        self.runner.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.logger.info("任务配置已生效，主调度线程启动...", "任务调度")

    def stop_task(self):
        if self.runner and self.runner.is_alive():
            self.runner.stop()
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def append_log(self, msg, status):
        log_line = f"[{status}] {msg}"
        self.log_text.append(log_line)
        vsb = self.log_text.verticalScrollBar()
        vsb.setValue(vsb.maximum())
