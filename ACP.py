import sys
import subprocess
import json
import os
import signal
import time
import threading
import webbrowser
import queue
from PySide6.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel,
    QHBoxLayout, QVBoxLayout, QFileDialog, QMessageBox, QStackedLayout,
    QDialog, QLineEdit, QFormLayout, QDialogButtonBox, QProgressBar,
    QListWidget, QListWidgetItem, QCheckBox, QVBoxLayout, QHBoxLayout
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QFont, QIcon, QBrush, QPainter, QLinearGradient, QPen

# Windows-specific imports for console capture
try:
    import win32api
    import win32console
    import win32process
    import win32pipe
    import win32file
    WINDOWS_CONSOLE_AVAILABLE = True
except ImportError:
    WINDOWS_CONSOLE_AVAILABLE = False

# Create folders for config and logs
CONFIG_DIR = "config"
LOG_DIR = "logs"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
LOG_FILE = os.path.join(LOG_DIR, "mysql_process.log")

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

class GradientLabel(QLabel):
    """Custom QLabel that renders text with a gradient effect"""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._gradient_start_color = "#404040"  # Dark grey
        self._gradient_end_color = "#666666"    # Light grey
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Create gradient
        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0, self._gradient_start_color)
        gradient.setColorAt(1, self._gradient_end_color)
        
        # Set gradient as pen for text
        painter.setPen(QPen(gradient, 1))
        
        # Set font
        painter.setFont(self.font())
        
        # Draw text with gradient
        painter.drawText(self.rect(), self.alignment(), self.text())
        
    def setGradientColors(self, start_color, end_color):
        """Set the gradient colors"""
        self._gradient_start_color = start_color
        self._gradient_end_color = end_color
        self.update()  # Trigger repaint

class MySQLConnectionDialog(QDialog):
    """Dialog for MySQL connection settings"""
    def __init__(self, parent=None, include_databases=False):
        super().__init__(parent)
        self.include_databases = include_databases
        
        if include_databases:
            self.setWindowTitle("MySQL Connection & Database Settings")
            self.setFixedSize(350, 280)
        else:
            self.setWindowTitle("MySQL Connection Settings")
            self.setFixedSize(300, 200)
        
        self.setModal(True)
        
        # Create form layout
        layout = QFormLayout()
        
        # Create input fields
        self.host_edit = QLineEdit("localhost")
        self.port_edit = QLineEdit("3306")
        self.user_edit = QLineEdit("root")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        
        # Add basic fields to layout
        layout.addRow("Host:", self.host_edit)
        layout.addRow("Port:", self.port_edit)
        layout.addRow("Username:", self.user_edit)
        layout.addRow("Password:", self.password_edit)
        
        # Add database fields if needed
        if include_databases:
            self.auth_db_edit = QLineEdit("acore_auth")
            self.characters_db_edit = QLineEdit("acore_characters")
            
            layout.addRow("Auth Database:", self.auth_db_edit)
            layout.addRow("Characters Database:", self.characters_db_edit)
        
        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        # Set main layout
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(button_box)
        self.setLayout(main_layout)
    
    def get_connection_data(self):
        """Return connection data as dictionary"""
        data = {
            'host': self.host_edit.text().strip(),
            'port': self.port_edit.text().strip(),
            'user': self.user_edit.text().strip(),
            'password': self.password_edit.text()
        }
        
        if self.include_databases:
            data['auth_db'] = self.auth_db_edit.text().strip()
            data['characters_db'] = self.characters_db_edit.text().strip()
        
        return data

class DatabaseSelectionDialog(QDialog):
    """Dialog for selecting databases to backup"""
    def __init__(self, databases, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Databases to Backup")
        self.setFixedSize(400, 300)
        self.setModal(True)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Add instruction label
        instruction_label = QLabel("Select the databases you want to backup:")
        layout.addWidget(instruction_label)
        
        # Create database list with checkboxes
        self.database_list = QListWidget()
        for db_name in databases:
            item = QListWidgetItem()
            checkbox = QCheckBox(db_name)
            self.database_list.addItem(item)
            self.database_list.setItemWidget(item, checkbox)
        
        layout.addWidget(self.database_list)
        
        # Add select all/none buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_all_btn.clicked.connect(self.select_all)
        select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Add OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def select_all(self):
        """Select all databases"""
        for i in range(self.database_list.count()):
            item = self.database_list.item(i)
            checkbox = self.database_list.itemWidget(item)
            checkbox.setChecked(True)
    
    def select_none(self):
        """Select no databases"""
        for i in range(self.database_list.count()):
            item = self.database_list.item(i)
            checkbox = self.database_list.itemWidget(item)
            checkbox.setChecked(False)
    
    def get_selected_databases(self):
        """Return list of selected database names"""
        selected = []
        for i in range(self.database_list.count()):
            item = self.database_list.item(i)
            checkbox = self.database_list.itemWidget(item)
            if checkbox.isChecked():
                selected.append(checkbox.text())
        return selected

class BackupProgressDialog(QDialog):
    """Dialog showing backup progress"""
    def __init__(self, total_databases, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Backup Progress")
        self.setFixedSize(400, 150)
        self.setModal(True)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Preparing backup...")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(total_databases)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Current database label
        self.current_db_label = QLabel("")
        layout.addWidget(self.current_db_label)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.user_cancelled)
        layout.addWidget(self.cancel_button)
        
        self.setLayout(layout)
        
        # Flag to track if user cancelled
        self.cancelled = False
    
    def user_cancelled(self):
        """Handle user cancellation"""
        self._user_cancelled = True
        self.cancelled = True
        self.reject()
    
    def update_progress(self, current_db, current_index, total):
        """Update progress display"""
        self.status_label.setText(f"Backing up account {current_index + 1} of {total}")
        self.current_db_label.setText(f"Current: {current_db}")
        self.progress_bar.setValue(current_index + 1)
        
        # Process events to update the UI
        QApplication.processEvents()
        
        # Force a small delay to ensure UI updates are visible
        import time
        time.sleep(0.1)
    
    def closeEvent(self, event):
        """Handle close event"""
        # Only set cancelled if user actually cancelled (not when we close it programmatically)
        if hasattr(self, '_user_cancelled'):
            self.cancelled = True
        event.accept()

class RestoreFileSelectionDialog(QDialog):
    """Dialog for selecting backup files to restore"""
    def __init__(self, backup_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Backup Files to Restore")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Add instruction label
        instruction_label = QLabel("Select the backup files you want to restore:")
        layout.addWidget(instruction_label)
        
        # Create file list with checkboxes
        self.file_list = QListWidget()
        for file_path in backup_files:
            item = QListWidgetItem()
            checkbox = QCheckBox(os.path.basename(file_path))
            checkbox.setToolTip(file_path)  # Show full path on hover
            self.file_list.addItem(item)
            self.file_list.setItemWidget(item, checkbox)
        
        layout.addWidget(self.file_list)
        
        # Add select all/none buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_all_btn.clicked.connect(self.select_all)
        select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Add OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def select_all(self):
        """Select all backup files"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            checkbox.setChecked(True)
    
    def select_none(self):
        """Select no backup files"""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            checkbox.setChecked(False)
    
    def get_selected_files(self):
        """Return list of selected backup file paths"""
        selected = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            checkbox = self.file_list.itemWidget(item)
            if checkbox.isChecked():
                # Get the full path from the tooltip
                selected.append(checkbox.toolTip())
        return selected

class AccountSelectionDialog(QDialog):
    """Dialog for selecting accounts to backup character data"""
    def __init__(self, accounts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Accounts for Character Backup")
        self.setFixedSize(400, 400)
        self.setModal(True)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Add instruction label
        instruction_label = QLabel("Select the accounts whose character data you want to backup:")
        layout.addWidget(instruction_label)
        
        # Create account list with checkboxes
        self.account_list = QListWidget()
        for account in accounts:
            item = QListWidgetItem()
            checkbox = QCheckBox(f"{account['username']} (ID: {account['id']})")
            checkbox.setToolTip(f"Account: {account['username']}\nID: {account['id']}\nEmail: {account.get('email', 'N/A')}")
            self.account_list.addItem(item)
            self.account_list.setItemWidget(item, checkbox)
        
        layout.addWidget(self.account_list)
        
        # Add select all/none buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_none_btn = QPushButton("Select None")
        select_all_btn.clicked.connect(self.select_all)
        select_none_btn.clicked.connect(self.select_none)
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(select_none_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Add OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def select_all(self):
        """Select all accounts"""
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            checkbox = self.account_list.itemWidget(item)
            checkbox.setChecked(True)
    
    def select_none(self):
        """Select no accounts"""
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            checkbox = self.account_list.itemWidget(item)
            checkbox.setChecked(False)
    
    def get_selected_accounts(self):
        """Return list of selected account usernames"""
        selected = []
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            checkbox = self.account_list.itemWidget(item)
            if checkbox.isChecked():
                # Extract username from checkbox text (format: "username (ID: xxx)")
                username = checkbox.text().split(' (ID:')[0]
                selected.append(username)
        return selected

class RestoreProgressDialog(QDialog):
    """Dialog showing restore progress"""
    def __init__(self, total_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Database Restore Progress")
        self.setFixedSize(400, 150)
        self.setModal(True)
        
        # Create layout
        layout = QVBoxLayout()
        
        # Status label
        self.status_label = QLabel("Preparing restore...")
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(total_files)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Current file label
        self.current_file_label = QLabel("")
        layout.addWidget(self.current_file_label)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.user_cancelled)
        layout.addWidget(self.cancel_button)
        
        self.setLayout(layout)
        
        # Flag to track if user cancelled
        self.cancelled = False
    
    def user_cancelled(self):
        """Handle user cancellation"""
        self._user_cancelled = True
        self.cancelled = True
        self.reject()
    
    def update_progress(self, current_file, current_index, total):
        """Update progress display"""
        self.status_label.setText(f"Restoring database {current_index + 1} of {total}")
        self.current_file_label.setText(f"Current: {os.path.basename(current_file)}")
        self.progress_bar.setValue(current_index + 1)
        
        # Process events to update the UI
        QApplication.processEvents()
    
    def closeEvent(self, event):
        """Handle close event"""
        # Only set cancelled if user actually cancelled (not when we close it programmatically)
        if hasattr(self, '_user_cancelled'):
            self.cancelled = True
        event.accept()

class AccountManagementDialog(QDialog):
    """Dialog for account management - create and delete accounts"""
    def __init__(self, parent=None, mysql_host="", mysql_port="", mysql_user="", mysql_password="", auth_db=""):
        super().__init__(parent)
        self.setWindowTitle("Account Management")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        # Store database connection details
        self.mysql_host = mysql_host
        self.mysql_port = mysql_port
        self.mysql_user = mysql_user
        self.mysql_password = mysql_password
        self.auth_db = auth_db
        
        # Create layout
        layout = QVBoxLayout()
        
        # Create tab widget for different operations
        from PySide6.QtWidgets import QTabWidget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.create_account_tab()
        self.create_delete_account_tab()
        self.create_list_accounts_tab()
        
        layout.addWidget(self.tab_widget)
        
        # Add buttons
        button_layout = QHBoxLayout()
        self.execute_btn = QPushButton("Execute")
        self.execute_btn.clicked.connect(self.execute_command)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.execute_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Store current operation
        self.current_operation = "create"
    
    def create_account_tab(self):
        """Create the account creation tab"""
        create_widget = QWidget()
        create_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Create Account")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        create_layout.addWidget(title_label)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Username field
        self.create_username_edit = QLineEdit()
        self.create_username_edit.setPlaceholderText("Enter username")
        form_layout.addRow("Username:", self.create_username_edit)
        
        # Password field
        self.create_password_edit = QLineEdit()
        self.create_password_edit.setPlaceholderText("Enter password")
        self.create_password_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password:", self.create_password_edit)
        
        # Email field
        self.create_email_edit = QLineEdit()
        self.create_email_edit.setPlaceholderText("Enter email (optional)")
        form_layout.addRow("Email:", self.create_email_edit)
        
        # Level field - Dropdown instead of text input
        from PySide6.QtWidgets import QComboBox
        self.create_level_combo = QComboBox()
        self.create_level_combo.addItem("Player", 0)
        self.create_level_combo.addItem("Moderator", 1)
        self.create_level_combo.addItem("GM", 2)
        self.create_level_combo.addItem("Admin", 3)
        form_layout.addRow("Level:", self.create_level_combo)
        
        create_layout.addLayout(form_layout)
        
        # Info text
        info_label = QLabel("This will create a new account in the database with the specified details.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666666; font-style: italic;")
        create_layout.addWidget(info_label)
        
        create_widget.setLayout(create_layout)
        self.tab_widget.addTab(create_widget, "Create Account")
    
    def create_delete_account_tab(self):
        """Create the account deletion tab"""
        delete_widget = QWidget()
        delete_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Delete Account")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        delete_layout.addWidget(title_label)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Username field
        self.delete_username_edit = QLineEdit()
        self.delete_username_edit.setPlaceholderText("Enter username to delete")
        form_layout.addRow("Username:", self.delete_username_edit)
        
        delete_layout.addLayout(form_layout)
        
        # Warning text
        warning_label = QLabel("⚠️ WARNING: This will permanently delete the account and all associated data!")
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #ff0000; font-weight: bold;")
        delete_layout.addWidget(warning_label)
        
        # Info text
        info_label = QLabel("This will delete the account from the database.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666666; font-style: italic;")
        delete_layout.addWidget(info_label)
        
        delete_widget.setLayout(delete_layout)
        self.tab_widget.addTab(delete_widget, "Delete Account")
    
    def create_list_accounts_tab(self):
        """Create the list accounts tab"""
        list_widget = QWidget()
        list_layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("List Accounts")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        list_layout.addWidget(title_label)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh Account List")
        self.refresh_btn.clicked.connect(self.refresh_account_list)
        list_layout.addWidget(self.refresh_btn)
        
        # Account list
        self.account_list_widget = QListWidget()
        list_layout.addWidget(self.account_list_widget)
        
        # Info text
        info_label = QLabel("Click 'Refresh Account List' to load all accounts from the database.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666666; font-style: italic;")
        list_layout.addWidget(info_label)
        
        list_widget.setLayout(list_layout)
        self.tab_widget.addTab(list_widget, "List Accounts")
    
    def refresh_account_list(self):
        """Refresh the account list from database"""
        try:
            # Build mysql command to get accounts - use same pattern as CH backup
            cmd = [
                "mysql", 
                f"--host={self.mysql_host}", 
                f"--port={self.mysql_port}", 
                f"--user={self.mysql_user}"
            ]
            if self.mysql_password:
                cmd.append(f"--password={self.mysql_password}")
            cmd.extend(["-e", f"SELECT id, username, email FROM {self.auth_db}.account ORDER BY username;"])
            
            if sys.platform == "win32":
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                QMessageBox.warning(self, "Error", f"Failed to fetch accounts: {result.stderr}")
                return
            
            # Clear current list
            self.account_list_widget.clear()
            
            # Parse and display accounts - use same pattern as CH backup
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Check if we have data beyond header
                for line in lines[1:]:  # Skip header
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        account_id = parts[0]
                        username = parts[1]
                        email = parts[2] if len(parts) > 2 else 'N/A'
                        
                        item_text = f"{username} (ID: {account_id}, Email: {email})"
                        self.account_list_widget.addItem(item_text)
            
            QMessageBox.information(self, "Success", f"Loaded {self.account_list_widget.count()} accounts from database.")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to refresh account list: {str(e)}")
    
    def execute_command(self):
        """Execute the selected command"""
        current_tab = self.tab_widget.currentIndex()
        
        if current_tab == 0:  # Create Account
            self.execute_create_account()
        elif current_tab == 1:  # Delete Account
            self.execute_delete_account()
        elif current_tab == 2:  # List Accounts
            self.refresh_account_list()
    
    def execute_create_account(self):
        """Execute account creation"""
        username = self.create_username_edit.text().strip()
        password = self.create_password_edit.text()
        email = self.create_email_edit.text().strip()
        level_int = self.create_level_combo.currentData()  # Get the integer value from dropdown
        
        # Validate input
        if not username:
            QMessageBox.warning(self, "Invalid Input", "Please enter a username.")
            return
        
        if not password:
            QMessageBox.warning(self, "Invalid Input", "Please enter a password.")
            return
        
        # Check if account already exists
        try:
            check_cmd = [
                "mysql", 
                f"--host={self.mysql_host}", 
                f"--port={self.mysql_port}", 
                f"--user={self.mysql_user}"
            ]
            if self.mysql_password:
                check_cmd.append(f"--password={self.mysql_password}")
            check_cmd.extend(["-e", f"SELECT COUNT(*) FROM {self.auth_db}.account WHERE username = '{username.upper()}';"])
            
            if sys.platform == "win32":
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                count = int(result.stdout.strip().split('\n')[1])  # Get count from result
                if count > 0:
                    QMessageBox.warning(self, "Account Exists", f"Account '{username}' already exists in the database.")
                    return
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to check if account exists: {str(e)}")
            return
        
        # Create the account
        try:
            # Generate proper SRP6 salt and verifier for AzerothCore (BINARY(32) fields)
            import secrets
            import hashlib
            
            # Generate a random 32-byte salt (raw binary data for BINARY(32))
            salt_bytes = secrets.token_bytes(32)
            
            # AzerothCore SRP6 constants (exact values from PHP code)
            g = 7
            N = 0x894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7
            
            # Generate verifier using the exact same method as PHP calculateSRP6Verifier
            # Calculate first hash: SHA1(username + ':' + password) in uppercase
            h1 = hashlib.sha1(f"{username.upper()}:{password.upper()}".encode('utf-8')).digest()
            
            # Calculate second hash: SHA1(salt + h1)
            h2 = hashlib.sha1(salt_bytes + h1).digest()
            
            # Convert h2 to integer (little-endian, matching PHP's gmp_import with GMP_LSW_FIRST)
            x = int.from_bytes(h2, byteorder='little')
            
            # Calculate verifier = g^x mod N
            verifier_int = pow(g, x, N)
            
            # Convert back to byte array (little-endian, matching PHP's gmp_export with GMP_LSW_FIRST)
            # Calculate the number of bytes needed
            byte_length = (verifier_int.bit_length() + 7) // 8
            verifier_bytes = verifier_int.to_bytes(byte_length, byteorder='little')
            
            # Pad to 32 bytes with zeros on the RIGHT (little-endian padding)
            verifier_bytes = verifier_bytes.ljust(32, b'\x00')
            
            # Convert binary data to hex for MySQL BINARY fields
            salt_hex = salt_bytes.hex()
            verifier_hex = verifier_bytes.hex()
            
            # Debug: Print the values to help troubleshoot
            print(f"Debug - Username: {username.upper()}")
            print(f"Debug - Salt (hex): {salt_hex}")
            print(f"Debug - Verifier (hex): {verifier_hex}")
            
            email_value = f"'{email}'" if email and email.strip() else "''"
            insert_cmd = [
                "mysql", 
                f"--host={self.mysql_host}", 
                f"--port={self.mysql_port}", 
                f"--user={self.mysql_user}"
            ]
            if self.mysql_password:
                insert_cmd.append(f"--password={self.mysql_password}")
            insert_cmd.extend(["-e", f"INSERT INTO {self.auth_db}.account (username, salt, verifier, email, joindate) VALUES ('{username.upper()}', UNHEX('{salt_hex}'), UNHEX('{verifier_hex}'), {email_value}, NOW());"])
            
            if sys.platform == "win32":
                result = subprocess.run(insert_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                result = subprocess.run(insert_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Get the account ID that was just created
                account_id_cmd = [
                    "mysql", 
                    f"--host={self.mysql_host}", 
                    f"--port={self.mysql_port}", 
                    f"--user={self.mysql_user}"
                ]
                if self.mysql_password:
                    account_id_cmd.append(f"--password={self.mysql_password}")
                account_id_cmd.extend(["-e", f"SELECT id FROM {self.auth_db}.account WHERE username = '{username.upper()}' ORDER BY id DESC LIMIT 1;"])
                
                if sys.platform == "win32":
                    account_id_result = subprocess.run(account_id_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    account_id_result = subprocess.run(account_id_cmd, capture_output=True, text=True, timeout=30)
                
                if account_id_result.returncode == 0:
                    # Parse the account ID
                    lines = account_id_result.stdout.strip().split('\n')
                    print(f"Debug - Account ID query result: {account_id_result.stdout}")
                    if len(lines) > 1:
                        account_id = lines[1].strip()
                        print(f"Debug - Account ID: {account_id}, Level: {level_int}")
                        
                        # If level is greater than 0, add to account_access table
                        if level_int > 0:
                            # Find the correct column names in account_access table
                            # First, let's check the table structure
                            structure_cmd = [
                                "mysql", 
                                f"--host={self.mysql_host}", 
                                f"--port={self.mysql_port}", 
                                f"--user={self.mysql_user}"
                            ]
                            if self.mysql_password:
                                structure_cmd.append(f"--password={self.mysql_password}")
                            structure_cmd.extend(["-e", f"DESCRIBE {self.auth_db}.account_access;"])
                            
                            if sys.platform == "win32":
                                structure_result = subprocess.run(structure_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                            else:
                                structure_result = subprocess.run(structure_cmd, capture_output=True, text=True, timeout=30)
                            
                            if structure_result.returncode == 0:
                                # Parse the structure to find the correct column names
                                structure_lines = structure_result.stdout.strip().split('\n')
                                print(f"Debug - Table structure: {structure_result.stdout}")
                                id_column = "id"
                                level_column = "level"
                                realm_column = "realm"
                                
                                for line in structure_lines[1:]:  # Skip header
                                    parts = line.strip().split('\t')
                                    if len(parts) >= 2:
                                        column_name = parts[0].strip()
                                        if column_name.lower() == "id":
                                            id_column = column_name
                                        elif "gmlevel" in column_name.lower():
                                            level_column = column_name
                                        elif "realmid" in column_name.lower():
                                            realm_column = column_name
                                
                                print(f"Debug - Using columns: {id_column}, {level_column}, {realm_column}")
                                
                                # Insert into account_access table
                                access_insert_cmd = [
                                    "mysql", 
                                    f"--host={self.mysql_host}", 
                                    f"--port={self.mysql_port}", 
                                    f"--user={self.mysql_user}"
                                ]
                                if self.mysql_password:
                                    access_insert_cmd.append(f"--password={self.mysql_password}")
                                
                                insert_query = f"INSERT INTO {self.auth_db}.account_access ({id_column}, {level_column}, {realm_column}) VALUES ({account_id}, {level_int}, -1);"
                                print(f"Debug - Insert query: {insert_query}")
                                access_insert_cmd.extend(["-e", insert_query])
                                
                                if sys.platform == "win32":
                                    access_result = subprocess.run(access_insert_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                                else:
                                    access_result = subprocess.run(access_insert_cmd, capture_output=True, text=True, timeout=30)
                                
                                print(f"Debug - Access insert result: returncode={access_result.returncode}, stdout={access_result.stdout}, stderr={access_result.stderr}")
                                
                                if access_result.returncode != 0:
                                    print(f"Warning: Failed to add account access: {access_result.stderr}")
                                else:
                                    print(f"Success: Account access added successfully!")
                            else:
                                print(f"Debug - Failed to get table structure: {structure_result.stderr}")
                        else:
                            print(f"Debug - Level is {level_int}, skipping account_access table (only levels > 0 are added)")
                
                QMessageBox.information(self, "Success", f"Account '{username}' created successfully!")
                # Clear form
                self.create_username_edit.clear()
                self.create_password_edit.clear()
                self.create_email_edit.clear()
                self.create_level_combo.setCurrentIndex(0)  # Reset to Player
            else:
                QMessageBox.warning(self, "Error", f"Failed to create account: {result.stderr}")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create account: {str(e)}")
    
    def execute_delete_account(self):
        """Execute account deletion"""
        username = self.delete_username_edit.text().strip()
        
        # Validate input
        if not username:
            QMessageBox.warning(self, "Invalid Input", "Please enter a username.")
            return
        
        # Check if account exists (simple check like CH backup does)
        try:
            verify_cmd = [
                "mysql", 
                f"--host={self.mysql_host}", 
                f"--port={self.mysql_port}", 
                f"--user={self.mysql_user}"
            ]
            if self.mysql_password:
                verify_cmd.append(f"--password={self.mysql_password}")
            verify_cmd.extend(["-e", f"SELECT COUNT(*) FROM {self.auth_db}.account WHERE username = '{username}';"])
            
            if sys.platform == "win32":
                result = subprocess.run(verify_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                result = subprocess.run(verify_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                count = int(result.stdout.strip().split('\n')[1])  # Get count from result
                if count == 0:
                    QMessageBox.warning(self, "Account Not Found", f"Account '{username}' not found in database.")
                    return
            else:
                QMessageBox.warning(self, "Error", f"Failed to verify account: {result.stderr}")
                return
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to verify account: {str(e)}")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Confirm Deletion", 
            f"Are you sure you want to permanently delete the account '{username}'?\n\nThis action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # Delete the account
                delete_cmd = [
                    "mysql", 
                    f"--host={self.mysql_host}", 
                    f"--port={self.mysql_port}", 
                    f"--user={self.mysql_user}"
                ]
                if self.mysql_password:
                    delete_cmd.append(f"--password={self.mysql_password}")
                delete_cmd.extend(["-e", f"DELETE FROM {self.auth_db}.account WHERE username = '{username}';"])
                
                if sys.platform == "win32":
                    result = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    result = subprocess.run(delete_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    QMessageBox.information(self, "Success", f"Account '{username}' deleted successfully!")
                    # Clear form
                    self.delete_username_edit.clear()
                else:
                    QMessageBox.warning(self, "Error", f"Failed to delete account: {result.stderr}")
                    
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete account: {str(e)}")

class MySQLProcessThread(QThread):
    log_signal = Signal(str)
    memory_signal = Signal(str)
    
    def __init__(self, mysql_path):
        super().__init__()
        self.mysql_path = mysql_path
        self.process = None
        self.memory_monitor_running = False
        
    def run(self):
        try:
            # Clear the log file at startup
            with open(LOG_FILE, "w") as log_file:
                log_file.write(f"--- MySQL Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Log cleared at startup ---\n")
                log_file.write(f"--- MySQL executable: {self.mysql_path} ---\n")
                log_file.write("=" * 80 + "\n")
                
                # Check if the path points to mysqld.exe (server) or mysql.exe (client)
                mysql_exe = os.path.basename(self.mysql_path).lower()
                if mysql_exe == "mysql.exe":
                    # If it's mysql.exe, we need to start mysqld.exe instead
                    mysqld_path = os.path.join(os.path.dirname(self.mysql_path), "mysqld.exe")
                    if os.path.exists(mysqld_path):
                        self.process = subprocess.Popen(
                            [mysqld_path, "--console"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        # Fallback to original path
                        self.process = subprocess.Popen(
                            [self.mysql_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                else:
                    # Use the original path with --console flag for mysqld
                    if mysql_exe == "mysqld.exe":
                        self.process = subprocess.Popen(
                            [self.mysql_path, "--console"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                    else:
                        # For other executables, use without --console
                        self.process = subprocess.Popen(
                            [self.mysql_path],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                
                # Log output in real-time from both stdout and stderr
                
                output_queue = queue.Queue()
                
                def read_output(pipe, prefix):
                    try:
                        for line in iter(pipe.readline, ''):
                            if line:
                                output_queue.put(f"[{prefix}] {line}")
                    except Exception:
                        pass
                
                # Memory monitoring will be handled by the main UI thread
                pass
                
                # Start threads to read stdout and stderr
                stdout_thread = threading.Thread(target=read_output, args=(self.process.stdout, "STDOUT"))
                stderr_thread = threading.Thread(target=read_output, args=(self.process.stderr, "STDERR"))
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # Process output from both streams
                while self.process.poll() is None:
                    try:
                        # Get output with timeout
                        output = output_queue.get(timeout=0.1)
                        if output:
                            log_file.write(output)
                            log_file.flush()
                            self.log_signal.emit(output.strip())
                    except queue.Empty:
                        continue
                    except Exception:
                        break
                
                # Wait for threads to finish
                stdout_thread.join(timeout=1)
                stderr_thread.join(timeout=1)
                
                # Stop memory monitoring
                self.memory_monitor_running = False
                        
        except Exception as e:
            error_msg = f"Error starting MySQL: {str(e)}"
            with open(LOG_FILE, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"{error_msg}\n")
            self.log_signal.emit(error_msg)
    
    # Memory monitoring is now handled by the main UI thread
    pass
    
    def stop_process(self):
        if self.process:
            try:
                with open(LOG_FILE, "a") as log_file:
                    log_file.write(f"\n--- Starting safe MySQL shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                
                # Step 1: Try graceful shutdown - safest method
                if sys.platform == "win32":
                    # On Windows, start with SIGTERM (terminate) which is safer
                    self.process.terminate()
                else:
                    # On Unix-like systems, use SIGINT (CTRL+C equivalent)
                    self.process.send_signal(signal.SIGINT)
                
                # Wait up to 15 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=15)
                    with open(LOG_FILE, "a") as log_file:
                        if sys.platform == "win32":
                            log_file.write(f"--- MySQL stopped gracefully with SIGTERM ---\n")
                        else:
                            log_file.write(f"--- MySQL stopped gracefully with SIGINT ---\n")
                except subprocess.TimeoutExpired:
                    with open(LOG_FILE, "a") as log_file:
                        if sys.platform == "win32":
                            log_file.write(f"--- SIGTERM timeout, using force kill as last resort ---\n")
                        else:
                            log_file.write(f"--- SIGINT timeout, trying SIGTERM ---\n")
                    
                    # Step 2: On Unix, try SIGTERM if SIGINT didn't work
                    if sys.platform != "win32":
                        self.process.terminate()
                        
                        # Wait up to 10 seconds for graceful shutdown with SIGTERM
                        try:
                            self.process.wait(timeout=10)
                            with open(LOG_FILE, "a") as log_file:
                                log_file.write(f"--- MySQL stopped gracefully with SIGTERM ---\n")
                        except subprocess.TimeoutExpired:
                            with open(LOG_FILE, "a") as log_file:
                                log_file.write(f"--- SIGTERM timeout, using force kill as last resort ---\n")
                    
                    # Step 3: Force kill only as absolute last resort
                    self.process.kill()
                    self.process.wait()
                    with open(LOG_FILE, "a") as log_file:
                        log_file.write(f"--- MySQL force killed ---\n")
                
                with open(LOG_FILE, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- MySQL Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    
            except Exception as e:
                error_msg = f"Error stopping MySQL: {str(e)}"
                with open(LOG_FILE, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"{error_msg}\n")
        
        # Only use force kill for remaining processes as absolute last resort
        self._cleanup_remaining_processes()
    
    def _cleanup_remaining_processes(self):
        """Safely cleanup any remaining MySQL processes"""
        try:
            with open(LOG_FILE, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Checking for remaining MySQL processes ---\n")
            
            if sys.platform == "win32":
                # First try graceful termination without /f flag
                subprocess.run(["taskkill", "/im", "mysqld.exe"], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                subprocess.run(["taskkill", "/im", "mysql.exe"], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Wait a moment, then check if processes are still running
                time.sleep(2)
                
                # Only use force kill if processes are still running
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" in result.stdout:
                    with open(LOG_FILE, "a") as log_file:
                        log_file.write("=" * 80 + "\n")
                        log_file.write(f"--- Force killing remaining mysqld.exe processes ---\n")
                    subprocess.run(["taskkill", "/f", "/im", "mysqld.exe"], 
                                 capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysql.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysql.exe" in result.stdout:
                    with open(LOG_FILE, "a") as log_file:
                        log_file.write("=" * 80 + "\n")
                        log_file.write(f"--- Force killing remaining mysql.exe processes ---\n")
                    subprocess.run(["taskkill", "/f", "/im", "mysql.exe"], 
                                 capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # On Unix-like systems, try SIGTERM first, then SIGKILL
                subprocess.run(["pkill", "-TERM", "-f", "mysqld"], capture_output=True)
                subprocess.run(["pkill", "-TERM", "-f", "mysql"], capture_output=True)
                
                # Wait a moment, then force kill if still running
                time.sleep(2)
                subprocess.run(["pkill", "-KILL", "-f", "mysqld"], capture_output=True)
                subprocess.run(["pkill", "-KILL", "-f", "mysql"], capture_output=True)
                
        except Exception as e:
            with open(LOG_FILE, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Cleanup error: {str(e)} ---\n")

class AuthServerProcessThread(QThread):
    log_signal = Signal(str)
    memory_signal = Signal(str)
    
    def __init__(self, auth_path):
        super().__init__()
        self.auth_path = auth_path
        self.process = None
        self.memory_monitor_running = False
        
    def run(self):
        try:
            # Create AuthServer-specific log file
            auth_log_file = os.path.join(LOG_DIR, "authserver_process.log")
            
            # Clear the log file at startup
            with open(auth_log_file, "w") as log_file:
                log_file.write(f"--- AuthServer Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Log cleared at startup ---\n")
                log_file.write(f"--- AuthServer executable: {self.auth_path} ---\n")
                log_file.write("=" * 80 + "\n")
            
            # Start AuthServer with minimal parameters - no pipes, no complex threading
            # This is the same simple approach that works for WorldServer
            auth_path_abs = os.path.abspath(self.auth_path)
            
            # Debug information
            with open(auth_log_file, "a") as log_file:
                log_file.write(f"--- Attempting to start AuthServer ---\n")
                log_file.write(f"--- Absolute path: {auth_path_abs} ---\n")
                log_file.write(f"--- Working directory: {os.path.dirname(auth_path_abs)} ---\n")
                log_file.write(f"--- File exists: {os.path.exists(auth_path_abs)} ---\n")
                log_file.write(f"--- File size: {os.path.getsize(auth_path_abs) if os.path.exists(auth_path_abs) else 'N/A'} ---\n")
            
            self.process = subprocess.Popen(
                [auth_path_abs],
                cwd=os.path.dirname(auth_path_abs),
                shell=True
            )
            
            # Log process start
            with open(auth_log_file, "a") as log_file:
                log_file.write(f"--- Process started with PID: {self.process.pid} ---\n")
                log_file.write(f"--- Working directory: {os.path.dirname(auth_path_abs)} ---\n")
            
            # Memory monitoring will be handled by the main UI thread
            pass
            
            # Simply wait for the process to finish
            return_code = self.process.wait()
            
            # Stop memory monitoring
            if hasattr(self, 'memory_timer'):
                self.memory_timer.stop()
            
            # Log process end
            with open(auth_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- AuthServer Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Return code: {return_code} ---\n")
                log_file.write("=" * 80 + "\n")
                        
        except Exception as e:
            error_msg = f"Error starting AuthServer: {str(e)}"
            with open(auth_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"{error_msg}\n")
            self.log_signal.emit(error_msg)
    
    # Memory monitoring is now handled by the main UI thread
    pass
    
    def stop_process(self):
        if self.process:
            try:
                auth_log_file = os.path.join(LOG_DIR, "authserver_process.log")
                
                with open(auth_log_file, "a") as log_file:
                    log_file.write(f"\n--- Starting AuthServer shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                
                # Simple terminate and wait
                self.process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                    with open(auth_log_file, "a") as log_file:
                        log_file.write(f"--- AuthServer stopped gracefully ---\n")
                except subprocess.TimeoutExpired:
                    with open(auth_log_file, "a") as log_file:
                        log_file.write(f"--- Timeout, force killing AuthServer ---\n")
                    # Force kill if timeout
                    self.process.kill()
                    self.process.wait()
                
                with open(auth_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- AuthServer Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    
            except Exception as e:
                error_msg = f"Error stopping AuthServer: {str(e)}"
                with open(auth_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"{error_msg}\n")
        
        # Only use force kill for remaining processes as absolute last resort
        self._cleanup_remaining_processes()
    
    def _cleanup_remaining_processes(self):
        """Safely cleanup any remaining AuthServer processes"""
        try:
            auth_log_file = os.path.join(LOG_DIR, "authserver_process.log")
            with open(auth_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Checking for remaining AuthServer processes ---\n")
            
            if sys.platform == "win32":
                # First try graceful termination without /f flag
                subprocess.run(["taskkill", "/im", "authserver.exe"], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Wait a moment, then check if processes are still running
                time.sleep(2)
                
                # Only use force kill if processes are still running
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq authserver.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "authserver.exe" in result.stdout:
                    with open(auth_log_file, "a") as log_file:
                        log_file.write("=" * 80 + "\n")
                        log_file.write(f"--- Force killing remaining authserver.exe processes ---\n")
                    subprocess.run(["taskkill", "/f", "/im", "authserver.exe"], 
                                 capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # On Unix-like systems, try SIGTERM first, then SIGKILL
                subprocess.run(["pkill", "-TERM", "-f", "authserver"], capture_output=True)
                
                # Wait a moment, then force kill if still running
                time.sleep(2)
                subprocess.run(["pkill", "-KILL", "-f", "authserver"], capture_output=True)
                
        except Exception as e:
            with open(auth_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Cleanup error: {str(e)} ---\n")

class WorldServerProcessThread(QThread):
    log_signal = Signal(str)
    memory_signal = Signal(str)
    
    def __init__(self, world_path):
        super().__init__()
        self.world_path = world_path
        self.process = None
        self.memory_monitor_running = False
        
    def run(self):
        try:
            # Create WorldServer-specific log file
            world_log_file = os.path.join(LOG_DIR, "worldserver_process.log")
            
            # Clear the log file at startup
            with open(world_log_file, "w") as log_file:
                log_file.write(f"--- WorldServer Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Log cleared at startup ---\n")
                log_file.write(f"--- WorldServer executable: {self.world_path} ---\n")
                log_file.write("=" * 80 + "\n")
            
            # Start WorldServer with minimal parameters - no pipes, no complex threading
            # This is the most basic approach possible
            world_path_abs = os.path.abspath(self.world_path)
            
            # Debug information
            with open(world_log_file, "a") as log_file:
                log_file.write(f"--- Attempting to start WorldServer ---\n")
                log_file.write(f"--- Absolute path: {world_path_abs} ---\n")
                log_file.write(f"--- Working directory: {os.path.dirname(world_path_abs)} ---\n")
                log_file.write(f"--- File exists: {os.path.exists(world_path_abs)} ---\n")
                log_file.write(f"--- File size: {os.path.getsize(world_path_abs) if os.path.exists(world_path_abs) else 'N/A'} ---\n")
            
            self.process = subprocess.Popen(
                [world_path_abs],
                cwd=os.path.dirname(world_path_abs),
                shell=True
            )
            
            # Log process start
            with open(world_log_file, "a") as log_file:
                log_file.write(f"--- Process started with PID: {self.process.pid} ---\n")
                log_file.write(f"--- Working directory: {os.path.dirname(self.world_path)} ---\n")
            
            # Memory monitoring will be handled by the main UI thread
            pass
            
            # Simply wait for the process to finish
            return_code = self.process.wait()
            
            # Stop memory monitoring
            if hasattr(self, 'memory_timer'):
                self.memory_timer.stop()
            
            # Log process end
            with open(world_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- WorldServer Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Return code: {return_code} ---\n")
                log_file.write("=" * 80 + "\n")
                        
        except Exception as e:
            error_msg = f"Error starting WorldServer: {str(e)}"
            with open(world_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"{error_msg}\n")
            self.log_signal.emit(error_msg)
    
    # Memory monitoring is now handled by the main UI thread
    pass
    
    def stop_process(self):
        if self.process:
            try:
                world_log_file = os.path.join(LOG_DIR, "worldserver_process.log")
                
                with open(world_log_file, "a") as log_file:
                    log_file.write(f"\n--- Starting WorldServer shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                
                # Simple terminate and wait
                self.process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    self.process.wait(timeout=10)
                    with open(world_log_file, "a") as log_file:
                        log_file.write(f"--- WorldServer stopped gracefully ---\n")
                except subprocess.TimeoutExpired:
                    with open(world_log_file, "a") as log_file:
                        log_file.write(f"--- Timeout, force killing WorldServer ---\n")
                    # Force kill if timeout
                    self.process.kill()
                    self.process.wait()
                
                with open(world_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- WorldServer Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    
            except Exception as e:
                error_msg = f"Error stopping WorldServer: {str(e)}"
                with open(world_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"{error_msg}\n")
        
        # Only use force kill for remaining processes as absolute last resort
        self._cleanup_remaining_processes()
    
    def _cleanup_remaining_processes(self):
        """Safely cleanup any remaining WorldServer processes"""
        try:
            world_log_file = os.path.join(LOG_DIR, "worldserver_process.log")
            with open(world_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Checking for remaining WorldServer processes ---\n")
            
            if sys.platform == "win32":
                # First try graceful termination without /f flag
                subprocess.run(["taskkill", "/im", "worldserver.exe"], 
                             capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                
                # Wait a moment, then check if processes are still running
                time.sleep(2)
                
                # Only use force kill if processes are still running
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq worldserver.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "worldserver.exe" in result.stdout:
                    with open(world_log_file, "a") as log_file:
                        log_file.write("=" * 80 + "\n")
                        log_file.write(f"--- Force killing remaining worldserver.exe processes ---\n")
                    subprocess.run(["taskkill", "/f", "/im", "worldserver.exe"], 
                                 capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                # On Unix-like systems, try SIGTERM first, then SIGKILL
                subprocess.run(["pkill", "-TERM", "-f", "worldserver"], capture_output=True)
                
                # Wait a moment, then force kill if still running
                time.sleep(2)
                subprocess.run(["pkill", "-KILL", "-f", "worldserver"], capture_output=True)
                
        except Exception as e:
            with open(world_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Cleanup error: {str(e)} ---\n")

class ClientProcessThread(QThread):
    log_signal = Signal(str)

    def __init__(self, client_path):
        super().__init__()
        self.client_path = client_path
        self.process = None

    def run(self):
        try:
            client_log_file = os.path.join(LOG_DIR, "client_process.log")

            with open(client_log_file, "w") as log_file:
                log_file.write(f"--- Client Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Log cleared at startup ---\n")
                log_file.write(f"--- Client executable: {self.client_path} ---\n")
                log_file.write("=" * 80 + "\n")

                client_path_abs = os.path.abspath(self.client_path)
                with open(client_log_file, "a") as lf:
                    lf.write(f"--- Attempting to start Client ---\n")
                    lf.write(f"--- Absolute path: {client_path_abs} ---\n")
                    lf.write(f"--- Working directory: {os.path.dirname(client_path_abs)} ---\n")
                    lf.write(f"--- File exists: {os.path.exists(client_path_abs)} ---\n")
                    lf.write(f"--- File size: {os.path.getsize(client_path_abs) if os.path.exists(client_path_abs) else 'N/A'} ---\n")

                self.process = subprocess.Popen(
                    [client_path_abs],
                    cwd=os.path.dirname(client_path_abs),
                    shell=True
                )

                with open(client_log_file, "a") as lf:
                    lf.write(f"--- Process started with PID: {self.process.pid} ---\n")
                    lf.write(f"--- Working directory: {os.path.dirname(client_path_abs)} ---\n")

                return_code = self.process.wait()

                with open(client_log_file, "a") as lf:
                    lf.write("=" * 80 + "\n")
                    lf.write(f"--- Client Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    lf.write(f"--- Return code: {return_code} ---\n")
                    lf.write("=" * 80 + "\n")

        except Exception as e:
            client_log_file = os.path.join(LOG_DIR, "client_process.log")
            error_msg = f"Error starting Client: {str(e)}"
            with open(client_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"{error_msg}\n")
            self.log_signal.emit(error_msg)

    def stop_process(self):
        if self.process:
            try:
                client_log_file = os.path.join(LOG_DIR, "client_process.log")
                with open(client_log_file, "a") as log_file:
                    log_file.write(f"\n--- Starting Client shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                    with open(client_log_file, "a") as log_file:
                        log_file.write(f"--- Client stopped gracefully ---\n")
                except subprocess.TimeoutExpired:
                    with open(client_log_file, "a") as log_file:
                        log_file.write(f"--- Timeout, force killing Client ---\n")
                    self.process.kill()
                    self.process.wait()

                with open(client_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- Client Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            except Exception as e:
                client_log_file = os.path.join(LOG_DIR, "client_process.log")
                error_msg = f"Error stopping Client: {str(e)}"
                with open(client_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"{error_msg}\n")

class WebServerProcessThread(QThread):
    log_signal = Signal(str)

    def __init__(self, web_path):
        super().__init__()
        self.web_path = web_path
        self.process = None

    def run(self):
        try:
            web_log_file = os.path.join(LOG_DIR, "webserver_process.log")

            with open(web_log_file, "w") as log_file:
                log_file.write(f"--- Webserver Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                log_file.write(f"--- Log cleared at startup ---\n")
                log_file.write(f"--- Webserver executable: {self.web_path} ---\n")
                log_file.write("=" * 80 + "\n")

                web_path_abs = os.path.abspath(self.web_path)
                with open(web_log_file, "a") as lf:
                    lf.write(f"--- Attempting to start Webserver ---\n")
                    lf.write(f"--- Absolute path: {web_path_abs} ---\n")
                    lf.write(f"--- Working directory: {os.path.dirname(web_path_abs)} ---\n")
                    lf.write(f"--- File exists: {os.path.exists(web_path_abs)} ---\n")
                    lf.write(f"--- File size: {os.path.getsize(web_path_abs) if os.path.exists(web_path_abs) else 'N/A'} ---\n")

                self.process = subprocess.Popen(
                    [web_path_abs],
                    cwd=os.path.dirname(web_path_abs),
                    shell=True
                )

                with open(web_log_file, "a") as lf:
                    lf.write(f"--- Process started with PID: {self.process.pid} ---\n")
                    lf.write(f"--- Working directory: {os.path.dirname(web_path_abs)} ---\n")

                return_code = self.process.wait()

                with open(web_log_file, "a") as lf:
                    lf.write("=" * 80 + "\n")
                    lf.write(f"--- Webserver Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                    lf.write(f"--- Return code: {return_code} ---\n")
                    lf.write("=" * 80 + "\n")

        except Exception as e:
            web_log_file = os.path.join(LOG_DIR, "webserver_process.log")
            error_msg = f"Error starting Webserver: {str(e)}"
            with open(web_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"{error_msg}\n")
            self.log_signal.emit(error_msg)

    def stop_process(self):
        if self.process:
            try:
                web_log_file = os.path.join(LOG_DIR, "webserver_process.log")
                with open(web_log_file, "a") as log_file:
                    log_file.write(f"\n--- Starting Webserver shutdown at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                    with open(web_log_file, "a") as log_file:
                        log_file.write(f"--- Webserver stopped gracefully ---\n")
                except subprocess.TimeoutExpired:
                    with open(web_log_file, "a") as log_file:
                        log_file.write(f"--- Timeout, force killing Webserver ---\n")
                    self.process.kill()
                    self.process.wait()

                with open(web_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- Webserver Stopped at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            except Exception as e:
                web_log_file = os.path.join(LOG_DIR, "webserver_process.log")
                error_msg = f"Error stopping Webserver: {str(e)}"
                with open(web_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"{error_msg}\n")
        # Ensure any lingering Apache processes are terminated
        self._cleanup_remaining_processes()

    def _cleanup_remaining_processes(self):
        """Safely cleanup any remaining Apache webserver processes on Windows"""
        try:
            web_log_file = os.path.join(LOG_DIR, "webserver_process.log")
            with open(web_log_file, "a") as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write(f"--- Checking for remaining Apache processes ---\n")

            if sys.platform == "win32":
                # Try graceful termination without /f first
                for image_name in ["httpd.exe", "apache.exe", "ApacheMonitor.exe"]:
                    try:
                        subprocess.run(["taskkill", "/im", image_name], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        pass

                # Wait briefly, then force kill if still running
                time.sleep(2)

                def image_is_running(name: str) -> bool:
                    try:
                        result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        return name.lower() in result.stdout.lower()
                    except Exception:
                        return False

                for image_name in ["httpd.exe", "apache.exe", "ApacheMonitor.exe"]:
                    if image_is_running(image_name):
                        with open(web_log_file, "a") as log_file:
                            log_file.write("=" * 80 + "\n")
                            log_file.write(f"--- Force killing remaining {image_name} processes ---\n")
                        try:
                            subprocess.run(["taskkill", "/f", "/im", image_name], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        except Exception:
                            pass
            else:
                # Unix-like fallback if ever used
                try:
                    subprocess.run(["pkill", "-TERM", "-f", "httpd"], capture_output=True)
                    time.sleep(2)
                    subprocess.run(["pkill", "-KILL", "-f", "httpd"], capture_output=True)
                except Exception:
                    pass
        except Exception as e:
            try:
                web_log_file = os.path.join(LOG_DIR, "webserver_process.log")
                with open(web_log_file, "a") as log_file:
                    log_file.write("=" * 80 + "\n")
                    log_file.write(f"--- Cleanup error: {str(e)} ---\n")
            except Exception:
                pass
class MySQLLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Azerothcore Control Panel")
        self.setFixedSize(700, 460)  # Increased height to accommodate work folders section
        
        # Set application icon (lazy loading)
        self.app_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        if os.path.isfile(self.app_icon_path):
            from PySide6.QtGui import QIcon
            self.setWindowIcon(QIcon(self.app_icon_path))
        
        # Initialize variables
        self.mysql_path = ""
        self.auth_path = ""
        self.world_path = ""
        self.client_path = ""
        self.web_path = ""
        
        # Editor paths
        self.heidi_path = ""
        self.keira_path = ""
        self.mpq_editor_path = ""
        self.wdbx_editor_path = ""
        self.spell_editor_path = ""
        self.notepad_plus_path = ""
        self.trinity_creator_path = ""
        
        # Other editor paths (second row)
        self.other_editor1_path = ""
        self.other_editor2_path = ""
        self.other_editor3_path = ""
        self.other_editor4_path = ""
        self.other_editor5_path = ""
        
        # Other editor button texts (second row)
        self.other_editor1_text = "Your app"
        self.other_editor2_text = "Your app"
        self.other_editor3_text = "Your app"
        self.other_editor4_text = "Your app"
        self.other_editor5_text = "Your app"
        self.process_thread = None
        self.auth_process_thread = None
        self.world_process_thread = None
        self.client_process_thread = None
        self.web_process_thread = None
        self.startup_timer = None
        self.auth_startup_timer = None
        self.world_startup_timer = None
        self.is_starting = False
        self.auth_is_starting = False
        self.world_is_starting = False
        self.client_is_starting = False
        self.web_is_starting = False
        # Memory monitoring removed
        
        # Countdown timer variables
        self.mysql_countdown_seconds = 0
        self.auth_countdown_seconds = 0
        self.world_countdown_seconds = 0
        self.client_countdown_seconds = 0
        self.web_countdown_seconds = 0
        
        # Autorestart checkbox state
        self.autorestart_enabled = False
        
        # Load configuration
        self.load_config()

        # Setup UI
        self.setup_ui()
        
        # Set button texts after UI is created
        self.update_other_editor_button_texts()
        
        # Optimize memory usage
        import gc
        gc.collect()  # Force garbage collection after UI setup
        
        # Setup status timer with longer interval to reduce CPU usage
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(3000)  # Further reduced to 3000ms for better performance
        
        # Setup countdown timer with 1 second interval
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Set to 1000ms to show every number
        
        # Memory monitoring removed
        
        # Initial status update
        self.show_startup_confirmation()
        self.update_status()
    
    def setup_ui(self):
        # Create main layout with three rows
        main_layout = QVBoxLayout()
        main_layout.setSpacing(0)  # Reduce spacing between rows
        main_layout.setContentsMargins(60, 0, 0, 0)  # Add 60px left margin
        
        # MySQL Row
        mysql_layout = QHBoxLayout()
        mysql_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        mysql_layout.setSpacing(0)  # Remove spacing
        
        # Database label
        self.db_label = GradientLabel("Database")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.db_label.setFont(font)
        self.db_label.setAlignment(Qt.AlignVCenter)
        self.db_label.setFixedWidth(100)  # Changed from 80 to 100 to match AuthServer label
        
        # MySQL Icon
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        
        # Get the script directory to find the icons folder
        script_dir = os.path.dirname(os.path.abspath(__file__))
        mysql_icon_path = os.path.join(script_dir, "icons", "mysql_icon.png")
        
        if os.path.isfile(mysql_icon_path):
            pixmap = QPixmap(mysql_icon_path)
            if not pixmap.isNull():
                self.icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.icon_label.setText("DB")
                self.icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.icon_label.setText("DB")
            self.icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # MySQL Start button
        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedSize(60, 30)
        self.start_btn.clicked.connect(self.start_mysql)
        
        # MySQL Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedSize(60, 30)
        self.stop_btn.clicked.connect(self.stop_mysql)
        self.stop_btn.setEnabled(False)
        
        # MySQL Path selector button
        self.path_btn = QPushButton("Path")
        self.path_btn.setFixedSize(60, 30)
        self.path_btn.clicked.connect(self.select_mysql_path)
        
        # MySQL Logs button
        self.logs_btn = QPushButton("Log")
        self.logs_btn.setFixedSize(60, 30)
        self.logs_btn.clicked.connect(self.open_logs)

        # MySQL Config button
        self.mysql_config_btn = QPushButton("Config")
        self.mysql_config_btn.setFixedSize(60, 30)
        self.mysql_config_btn.clicked.connect(self.open_mysql_config)
        
        # MySQL Folder button
        self.mysql_folder_btn = QPushButton()
        self.mysql_folder_btn.setFixedSize(40, 30)  # Increased width to match header
        self.mysql_folder_btn.setToolTip("Open MySQL folder")
        self.mysql_folder_btn.clicked.connect(self.open_mysql_folder)
        
        # Load folder icon
        folder_icon_path = os.path.join(script_dir, "icons", "folder_icon.png")
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.mysql_folder_btn.setIcon(QIcon(folder_icon_path))
                self.mysql_folder_btn.setIconSize(QSize(18, 18))  # Increased from 16x16 to 18x18
            else:
                self.mysql_folder_btn.setText("F")
                self.mysql_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.mysql_folder_btn.setText("F")
            self.mysql_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        # MySQL Status Container
        self.mysql_status_container = QWidget()
        self.mysql_status_container.setFixedSize(50, 30)  # Match Status header width
        self.mysql_status_container.setLayout(QHBoxLayout())
        self.mysql_status_container.layout().setContentsMargins(0, 0, 0, 0)
        self.mysql_status_container.layout().setSpacing(0)
        self.mysql_status_container.layout().addStretch()
        
        # MySQL Status LED
        self.status_led = QPushButton()
        self.status_led.setFixedSize(16, 16)
        self.status_led.setEnabled(False)  # Make it non-pushable
        self.status_led.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; border-radius: 8px; }")
        self.mysql_status_container.layout().addWidget(self.status_led)
        
        self.mysql_status_container.layout().addStretch()
        
        # MySQL Countdown Timer Container - Positioned to align with LED
        self.mysql_timer_container = QWidget()
        self.mysql_timer_container.setFixedSize(40, 30)  # Match Timer header width and button height
        
        # MySQL Countdown Timer with button-style frame
        self.mysql_countdown = QPushButton("")
        self.mysql_countdown.setFixedSize(40, 28)  # Height set to 28px
        self.mysql_countdown.setEnabled(False)  # Make it non-pushable
        self.mysql_countdown.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; color: #666666; }")
        countdown_font = QFont()
        countdown_font.setBold(True)
        countdown_font.setPointSize(10)
        self.mysql_countdown.setFont(countdown_font)
        
        # Set countdown directly in container
        self.mysql_timer_container.setLayout(QVBoxLayout())
        self.mysql_timer_container.layout().setContentsMargins(0, 0, 0, 0)
        self.mysql_timer_container.layout().setSpacing(0)
        self.mysql_timer_container.layout().addWidget(self.mysql_countdown)
        
        # MySQL Info Icon
        self.mysql_info_icon = QLabel()
        self.mysql_info_icon.setFixedSize(16, 16)
        self.mysql_info_icon.setToolTip("Push Path and choose mysqld.exe from the server/mysql/bin or server/database/bin folder.Config will open the my.ini usualy located in server/mysql or server/database folder.Log is autogenerated.Timer for opening mysql server is set to 10 sec.Folder Icon will open the selected path.Use Start/Stop to Open/Close application.Check restart box to autorestart server in case of crashes.")
        self.mysql_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Load info icon
        info_icon_path = os.path.join(script_dir, "icons", "info_icon.png")
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.mysql_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.mysql_info_icon.setText("i")
                self.mysql_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #ffff99;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            self.mysql_info_icon.setText("i")
            self.mysql_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #ffff99;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        
        self.mysql_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add MySQL widgets to layout
        mysql_layout.addWidget(self.db_label)
        mysql_layout.addWidget(self.icon_label)
        mysql_layout.addWidget(self.start_btn)
        mysql_layout.addWidget(self.stop_btn)
        mysql_layout.addWidget(self.path_btn)
        mysql_layout.addWidget(self.logs_btn)
        mysql_layout.addWidget(self.mysql_config_btn)
        mysql_layout.addWidget(self.mysql_folder_btn)
        mysql_layout.addWidget(self.mysql_status_container)
        mysql_layout.addWidget(self.mysql_timer_container)
        
        # Add spacing before info icon
        mysql_spacer = QLabel()
        mysql_spacer.setFixedSize(10, 30)  # Small spacer between counter and info icon
        
        mysql_layout.addWidget(mysql_spacer)
        mysql_layout.addWidget(self.mysql_info_icon)
        mysql_layout.addStretch()
        
        # AuthServer Row
        auth_layout = QHBoxLayout()
        auth_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        auth_layout.setSpacing(0)  # Remove spacing
        
        # AuthServer label
        self.auth_label = GradientLabel("AuthServer")
        self.auth_label.setFont(font)
        self.auth_label.setAlignment(Qt.AlignVCenter)
        self.auth_label.setFixedWidth(100)  # Increased from 80 to 100 to fit "AuthServer"
        
        # AuthServer Icon
        self.auth_icon_label = QLabel()
        self.auth_icon_label.setFixedSize(32, 32)
        
        auth_icon_path = os.path.join(script_dir, "icons", "auth_icon.png")
        
        if os.path.isfile(auth_icon_path):
            pixmap = QPixmap(auth_icon_path)
            if not pixmap.isNull():
                self.auth_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.auth_icon_label.setText("AS")
                self.auth_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.auth_icon_label.setText("AS")
            self.auth_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.auth_icon_label.setAlignment(Qt.AlignCenter)
        
        # AuthServer Start button
        self.auth_start_btn = QPushButton("Start")
        self.auth_start_btn.setFixedSize(60, 30)
        self.auth_start_btn.clicked.connect(self.start_authserver)
        
        # AuthServer Stop button
        self.auth_stop_btn = QPushButton("Stop")
        self.auth_stop_btn.setFixedSize(60, 30)
        self.auth_stop_btn.clicked.connect(self.stop_authserver)
        self.auth_stop_btn.setEnabled(False)
        
        # AuthServer Path selector button
        self.auth_path_btn = QPushButton("Path")
        self.auth_path_btn.setFixedSize(60, 30)
        self.auth_path_btn.clicked.connect(self.select_authserver_path)
        
        # AuthServer Logs button
        self.auth_logs_btn = QPushButton("Log")
        self.auth_logs_btn.setFixedSize(60, 30)
        self.auth_logs_btn.clicked.connect(self.open_auth_logs)
        
        # AuthServer Config button
        self.auth_config_btn = QPushButton("Config")
        self.auth_config_btn.setFixedSize(60, 30)
        self.auth_config_btn.clicked.connect(self.open_auth_config)
        
        # AuthServer Folder button
        self.auth_folder_btn = QPushButton()
        self.auth_folder_btn.setFixedSize(40, 30)  # Increased width to match header
        self.auth_folder_btn.setToolTip("Open AuthServer folder")
        self.auth_folder_btn.clicked.connect(self.open_auth_folder)
        
        # Load folder icon
        folder_icon_path = os.path.join(script_dir, "icons", "folder_icon.png")
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.auth_folder_btn.setIcon(QIcon(folder_icon_path))
                self.auth_folder_btn.setIconSize(QSize(18, 18))  # Increased from 16x16 to 18x18
            else:
                self.auth_folder_btn.setText("F")
                self.auth_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.auth_folder_btn.setText("F")
            self.auth_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        # AuthServer Status Container
        self.auth_status_container = QWidget()
        self.auth_status_container.setFixedSize(50, 30)  # Match Status header width
        self.auth_status_container.setLayout(QHBoxLayout())
        self.auth_status_container.layout().setContentsMargins(0, 0, 0, 0)
        self.auth_status_container.layout().setSpacing(0)
        self.auth_status_container.layout().addStretch()
        
        # AuthServer Status LED
        self.auth_status_led = QPushButton()
        self.auth_status_led.setFixedSize(16, 16)
        self.auth_status_led.setEnabled(False)  # Make it non-pushable
        self.auth_status_led.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; border-radius: 8px; }")
        self.auth_status_container.layout().addWidget(self.auth_status_led)
        
        self.auth_status_container.layout().addStretch()
        
        # AuthServer Countdown Timer Container - Positioned to align with LED
        self.auth_timer_container = QWidget()
        self.auth_timer_container.setFixedSize(40, 30)  # Match Timer header width and button height
        
        # AuthServer Countdown Timer with button-style frame
        self.auth_countdown = QPushButton("")
        self.auth_countdown.setFixedSize(40, 28)  # Height set to 28px
        self.auth_countdown.setEnabled(False)  # Make it non-pushable
        self.auth_countdown.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; color: #666666; }")
        self.auth_countdown.setFont(countdown_font)
        
        # Set countdown directly in container
        self.auth_timer_container.setLayout(QVBoxLayout())
        self.auth_timer_container.layout().setContentsMargins(0, 0, 0, 0)
        self.auth_timer_container.layout().setSpacing(0)
        self.auth_timer_container.layout().addWidget(self.auth_countdown)
        
        # AuthServer Info Icon
        self.auth_info_icon = QLabel()
        self.auth_info_icon.setFixedSize(16, 16)
        self.auth_info_icon.setToolTip("Push Path and choose authserver.exe from your server folder.Config will open the authserver.conf from your server/configs folder and Logs will open the authserver log file from yot server/Logs folder.Timer for opening authserver server is set to 10 sec.Folder Icon will open the selected path.Use Start/Stop to Open/Close application.Check restart box to autorestart server in case of crashes.")
        self.auth_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Load info icon for AuthServer
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.auth_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.auth_info_icon.setText("i")
                self.auth_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            self.auth_info_icon.setText("i")
            self.auth_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        
        self.auth_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add AuthServer widgets to layout
        auth_layout.addWidget(self.auth_label)
        auth_layout.addWidget(self.auth_icon_label)
        auth_layout.addWidget(self.auth_start_btn)
        auth_layout.addWidget(self.auth_stop_btn)
        auth_layout.addWidget(self.auth_path_btn)
        auth_layout.addWidget(self.auth_logs_btn)
        auth_layout.addWidget(self.auth_config_btn)
        auth_layout.addWidget(self.auth_folder_btn)
        auth_layout.addWidget(self.auth_status_container)
        auth_layout.addWidget(self.auth_timer_container)
        
        # Add spacing before info icon
        auth_spacer = QLabel()
        auth_spacer.setFixedSize(10, 30)  # Small spacer between counter and info icon
        
        auth_layout.addWidget(auth_spacer)
        auth_layout.addWidget(self.auth_info_icon)
        auth_layout.addStretch()
        
        # WorldServer Row
        world_layout = QHBoxLayout()
        world_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        world_layout.setSpacing(0)  # Remove spacing
        
        # WorldServer label
        self.world_label = GradientLabel("WorldServer")
        self.world_label.setFont(font)
        self.world_label.setAlignment(Qt.AlignVCenter)
        self.world_label.setFixedWidth(100)  # Same width as other labels
        
        # WorldServer Icon
        self.world_icon_label = QLabel()
        self.world_icon_label.setFixedSize(32, 32)
        
        world_icon_path = os.path.join(script_dir, "icons", "world_icon.png")
        
        if os.path.isfile(world_icon_path):
            pixmap = QPixmap(world_icon_path)
            if not pixmap.isNull():
                self.world_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.world_icon_label.setText("WS")
                self.world_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.world_icon_label.setText("WS")
            self.world_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.world_icon_label.setAlignment(Qt.AlignCenter)
        
        # WorldServer Start button
        self.world_start_btn = QPushButton("Start")
        self.world_start_btn.setFixedSize(60, 30)
        self.world_start_btn.clicked.connect(self.start_worldserver)
        
        # WorldServer Stop button
        self.world_stop_btn = QPushButton("Stop")
        self.world_stop_btn.setFixedSize(60, 30)
        self.world_stop_btn.clicked.connect(self.stop_worldserver)
        self.world_stop_btn.setEnabled(False)
        
        # WorldServer Path selector button
        self.world_path_btn = QPushButton("Path")
        self.world_path_btn.setFixedSize(60, 30)
        self.world_path_btn.clicked.connect(self.select_worldserver_path)
        
        # WorldServer Logs button
        self.world_logs_btn = QPushButton("Log")
        self.world_logs_btn.setFixedSize(60, 30)
        self.world_logs_btn.clicked.connect(self.open_world_logs)
        
        # WorldServer Config button
        self.world_config_btn = QPushButton("Config")
        self.world_config_btn.setFixedSize(60, 30)
        self.world_config_btn.clicked.connect(self.open_world_config)
        
        # WorldServer Folder button
        self.world_folder_btn = QPushButton()
        self.world_folder_btn.setFixedSize(40, 30)  # Increased width to match header
        self.world_folder_btn.setToolTip("Open WorldServer folder")
        self.world_folder_btn.clicked.connect(self.open_world_folder)
        
        # Load folder icon
        folder_icon_path = os.path.join(script_dir, "icons", "folder_icon.png")
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.world_folder_btn.setIcon(QIcon(folder_icon_path))
                self.world_folder_btn.setIconSize(QSize(18, 18))  # Increased from 16x16 to 18x18
            else:
                self.world_folder_btn.setText("F")
                self.world_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.world_folder_btn.setText("F")
            self.world_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        # WorldServer Status Container
        self.world_status_container = QWidget()
        self.world_status_container.setFixedSize(50, 30)  # Match Status header width
        self.world_status_container.setLayout(QHBoxLayout())
        self.world_status_container.layout().setContentsMargins(0, 0, 0, 0)
        self.world_status_container.layout().setSpacing(0)
        self.world_status_container.layout().addStretch()
        
        # WorldServer Status LED
        self.world_status_led = QPushButton()
        self.world_status_led.setFixedSize(16, 16)
        self.world_status_led.setEnabled(False)  # Make it non-pushable
        self.world_status_led.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; border-radius: 8px; }")
        self.world_status_container.layout().addWidget(self.world_status_led)
        
        self.world_status_container.layout().addStretch()
        
        # WorldServer Countdown Timer Container - Positioned to align with LED
        self.world_timer_container = QWidget()
        self.world_timer_container.setFixedSize(40, 30)  # Match Timer header width and button height
        
        # WorldServer Countdown Timer with button-style frame
        self.world_countdown = QPushButton("")
        self.world_countdown.setFixedSize(40, 28)  # Height set to 28px
        self.world_countdown.setEnabled(False)  # Make it non-pushable
        self.world_countdown.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; color: #666666; }")
        self.world_countdown.setFont(countdown_font)
        
        # Set countdown directly in container
        self.world_timer_container.setLayout(QVBoxLayout())
        self.world_timer_container.layout().setContentsMargins(0, 0, 0, 0)
        self.world_timer_container.layout().setSpacing(0)
        self.world_timer_container.layout().addWidget(self.world_countdown)
        
        # WorldServer Info Icon
        self.world_info_icon = QLabel()
        self.world_info_icon.setFixedSize(16, 16)
        self.world_info_icon.setToolTip("Push Path and choose worldserver.exe from your server folder.Config will open the worldserver.conf from your server/configs folder and Logs will open the worldserver log file from yot server/Logs folder.Timer for opening worldserver server is set to 120 sec.Folder Icon will open the selected path.Use Start/Stop to Open/Close application.Check restart box to autorestart server in case of crashes.")
        self.world_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Load info icon for WorldServer
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.world_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.world_info_icon.setText("i")
                self.world_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            self.world_info_icon.setText("i")
            self.world_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        
        self.world_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add WorldServer widgets to layout
        world_layout.addWidget(self.world_label)
        world_layout.addWidget(self.world_icon_label)
        world_layout.addWidget(self.world_start_btn)
        world_layout.addWidget(self.world_stop_btn)
        world_layout.addWidget(self.world_path_btn)
        world_layout.addWidget(self.world_logs_btn)
        world_layout.addWidget(self.world_config_btn)
        world_layout.addWidget(self.world_folder_btn)
        world_layout.addWidget(self.world_status_container)
        world_layout.addWidget(self.world_timer_container)
        
        # Add spacing before info icon
        world_spacer = QLabel()
        world_spacer.setFixedSize(10, 30)  # Small spacer between counter and info icon
        
        world_layout.addWidget(world_spacer)
        world_layout.addWidget(self.world_info_icon)
        world_layout.addStretch()
        
        # Create header row with column titles
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        header_layout.setSpacing(0)  # Remove spacing
        
        # Autorestart checkbox - positioned above Database label
        from PySide6.QtWidgets import QCheckBox
        self.autorestart_checkbox = QCheckBox("Autorestart")
        self.autorestart_checkbox.setFixedSize(100, 30)  # Match Database label width
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(10)
        self.autorestart_checkbox.setFont(header_font)
        self.autorestart_checkbox.setStyleSheet("""
            QCheckBox {
                color: #666666;
                spacing: 5px;
            }
        """)
        self.autorestart_checkbox.stateChanged.connect(self.on_autorestart_changed)
        header_layout.addWidget(self.autorestart_checkbox)
        
        # Icon spacer
        header_icon_spacer = QLabel("")
        header_icon_spacer.setFixedWidth(32)
        header_layout.addWidget(header_icon_spacer)
        
        # Start column title
        header_start_label = QLabel("Start")
        header_start_label.setAlignment(Qt.AlignCenter)
        header_start_label.setFixedWidth(60)
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(10)
        header_start_label.setFont(header_font)
        header_start_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_start_label)
        
        # Stop column title
        header_stop_label = QLabel("Stop")
        header_stop_label.setAlignment(Qt.AlignCenter)
        header_stop_label.setFixedWidth(60)
        header_stop_label.setFont(header_font)
        header_stop_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_stop_label)
        
        # Paths column title
        header_paths_label = QLabel("Paths")
        header_paths_label.setAlignment(Qt.AlignCenter)
        header_paths_label.setFixedWidth(60)
        header_paths_label.setFont(header_font)
        header_paths_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_paths_label)
        
        # Logs column title
        header_logs_label = QLabel("Logs")
        header_logs_label.setAlignment(Qt.AlignCenter)
        header_logs_label.setFixedWidth(60)
        header_logs_label.setFont(header_font)
        header_logs_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_logs_label)
        
        # Configs column title
        header_configs_label = QLabel("Configs")
        header_configs_label.setAlignment(Qt.AlignCenter)
        header_configs_label.setFixedWidth(60)
        header_configs_label.setFont(header_font)
        header_configs_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_configs_label)
        
        # Folder column title
        header_folder_label = QLabel("Folder")
        header_folder_label.setAlignment(Qt.AlignCenter)
        header_folder_label.setFixedWidth(40)  # Increased width for better visibility
        header_folder_label.setFont(header_font)
        header_folder_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_folder_label)
        
        # Status column title
        header_status_label = QLabel("Status")
        header_status_label.setAlignment(Qt.AlignCenter)
        header_status_label.setFixedWidth(50)
        header_status_label.setFont(header_font)
        header_status_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_status_label)
        
        # Timer column title
        header_timer_label = QLabel("Timer")
        header_timer_label.setAlignment(Qt.AlignCenter)
        header_timer_label.setFixedWidth(40)  # Increased width for better visibility
        header_timer_label.setFont(header_font)
        header_timer_label.setStyleSheet("color: #666666;")  # Subtle grey color
        header_layout.addWidget(header_timer_label)
        
        # Memory column removed
        
        header_layout.addStretch()
        
        # Add all rows to main layout
        main_layout.addLayout(header_layout)  # Header row
        main_layout.addLayout(mysql_layout)  # MySQL row
        
        # 2px spacer between server rows
        mysql_auth_spacer = QLabel()
        mysql_auth_spacer.setFixedHeight(2)
        main_layout.addWidget(mysql_auth_spacer)
        
        main_layout.addLayout(auth_layout)
        
        # 2px spacer between server rows
        auth_world_spacer = QLabel()
        auth_world_spacer.setFixedHeight(2)
        main_layout.addWidget(auth_world_spacer)
        
        main_layout.addLayout(world_layout)
        
        # 2px spacer between server rows
        world_client_spacer = QLabel()
        world_client_spacer.setFixedHeight(2)
        main_layout.addWidget(world_client_spacer)
        
        # Client Row
        client_layout = QHBoxLayout()
        client_layout.setContentsMargins(0, 0, 0, 0)
        client_layout.setSpacing(0)

        # Client label
        self.client_label = GradientLabel("Client")
        self.client_label.setFont(font)
        self.client_label.setAlignment(Qt.AlignVCenter)
        self.client_label.setFixedWidth(100)

        # Client icon
        self.client_icon_label = QLabel()
        self.client_icon_label.setFixedSize(32, 32)
        client_icon_path = os.path.join(script_dir, "icons", "client_icon.png")
        if os.path.isfile(client_icon_path):
            pixmap = QPixmap(client_icon_path)
            if not pixmap.isNull():
                self.client_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.client_icon_label.setText("CL")
                self.client_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.client_icon_label.setText("CL")
            self.client_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")

        # Client Start/Stop/Path/Log/Config/Folder
        self.client_start_btn = QPushButton("Start")
        self.client_start_btn.setFixedSize(60, 30)
        self.client_start_btn.clicked.connect(self.start_client)

        self.client_stop_btn = QPushButton("Stop")
        self.client_stop_btn.setFixedSize(60, 30)
        self.client_stop_btn.clicked.connect(self.stop_client)
        self.client_stop_btn.setEnabled(False)

        self.client_path_btn = QPushButton("Path")
        self.client_path_btn.setFixedSize(60, 30)
        self.client_path_btn.clicked.connect(self.select_client_path)

        self.client_logs_btn = QPushButton("Log")
        self.client_logs_btn.setFixedSize(60, 30)
        self.client_logs_btn.clicked.connect(self.open_client_logs)

        # Split Config into two buttons within a fixed 60x30 container
        self.client_config_container = QWidget()
        self.client_config_container.setFixedSize(60, 30)
        self.client_config_container.setLayout(QHBoxLayout())
        self.client_config_container.layout().setContentsMargins(0, 0, 0, 0)
        self.client_config_container.layout().setSpacing(0)

        self.client_wtf_btn = QPushButton("WTF")
        self.client_wtf_btn.setFixedSize(30, 30)
        self.client_wtf_btn.clicked.connect(self.open_client_config)

        self.client_rlm_btn = QPushButton("RLM")
        self.client_rlm_btn.setFixedSize(30, 30)
        self.client_rlm_btn.clicked.connect(self.open_client_realmlist)

        self.client_config_container.layout().addWidget(self.client_wtf_btn)
        self.client_config_container.layout().addWidget(self.client_rlm_btn)

        self.client_folder_btn = QPushButton()
        self.client_folder_btn.setFixedSize(40, 30)
        self.client_folder_btn.setToolTip("Open Client folder")
        self.client_folder_btn.clicked.connect(self.open_client_folder)
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.client_folder_btn.setIcon(QIcon(folder_icon_path))
                self.client_folder_btn.setIconSize(QSize(18, 18))
            else:
                self.client_folder_btn.setText("F")
                self.client_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.client_folder_btn.setText("F")
            self.client_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")

        # Client Status LED container
        self.client_status_container = QWidget()
        self.client_status_container.setFixedSize(50, 30)
        self.client_status_container.setLayout(QHBoxLayout())
        self.client_status_container.layout().setContentsMargins(0, 0, 0, 0)
        self.client_status_container.layout().setSpacing(0)
        self.client_status_container.layout().addStretch()

        self.client_status_led = QPushButton()
        self.client_status_led.setFixedSize(16, 16)
        self.client_status_led.setEnabled(False)
        self.client_status_led.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; border-radius: 8px; }")
        self.client_status_container.layout().addWidget(self.client_status_led)
        self.client_status_container.layout().addStretch()

        # Client Timer container and button-like label
        self.client_timer_container = QWidget()
        self.client_timer_container.setFixedSize(40, 30)

        self.client_countdown = QPushButton("")
        self.client_countdown.setFixedSize(40, 28)
        self.client_countdown.setEnabled(False)
        self.client_countdown.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; color: #666666; }")
        self.client_countdown.setFont(countdown_font)

        self.client_timer_container.setLayout(QVBoxLayout())
        self.client_timer_container.layout().setContentsMargins(0, 0, 0, 0)
        self.client_timer_container.layout().setSpacing(0)
        self.client_timer_container.layout().addWidget(self.client_countdown)

        # Client Info Icon
        self.client_info_icon = QLabel()
        self.client_info_icon.setFixedSize(16, 16)
        self.client_info_icon.setToolTip("Push Path and choose wow.exe from your client folder.Config WTF will open the config.wtf file from your client/WTF folder, RLM will open the realmlist.wtf file from your client/Data/enUS folder and Logs will open the logs folder from client/Logs .Timer for opening client is set to 15 sec.Folder Icon will open the selected path.Use Start/Stop to Open/Close application.")
        self.client_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Load info icon for Client
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.client_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.client_info_icon.setText("i")
                self.client_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            self.client_info_icon.setText("i")
            self.client_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        
        self.client_info_icon.setAlignment(Qt.AlignCenter)
        
        # Assemble client row
        client_layout.addWidget(self.client_label)
        client_layout.addWidget(self.client_icon_label)
        client_layout.addWidget(self.client_start_btn)
        client_layout.addWidget(self.client_stop_btn)
        client_layout.addWidget(self.client_path_btn)
        client_layout.addWidget(self.client_logs_btn)
        client_layout.addWidget(self.client_config_container)
        client_layout.addWidget(self.client_folder_btn)
        client_layout.addWidget(self.client_status_container)
        client_layout.addWidget(self.client_timer_container)
        
        # Add spacing before info icon
        client_spacer = QLabel()
        client_spacer.setFixedSize(10, 30)  # Small spacer between counter and info icon
        
        client_layout.addWidget(client_spacer)
        client_layout.addWidget(self.client_info_icon)
        client_layout.addStretch()

        main_layout.addLayout(client_layout)
        
        # 2px spacer between server rows
        client_web_spacer = QLabel()
        client_web_spacer.setFixedHeight(2)
        main_layout.addWidget(client_web_spacer)
        
        # Webserver Row
        web_layout = QHBoxLayout()
        web_layout.setContentsMargins(0, 0, 0, 0)
        web_layout.setSpacing(0)

        self.web_label = GradientLabel("Webserver")
        self.web_label.setFont(font)
        self.web_label.setAlignment(Qt.AlignVCenter)
        self.web_label.setFixedWidth(100)

        self.web_icon_label = QLabel()
        self.web_icon_label.setFixedSize(32, 32)
        web_icon_path = os.path.join(script_dir, "icons", "web_icon.png")
        if os.path.isfile(web_icon_path):
            pixmap = QPixmap(web_icon_path)
            if not pixmap.isNull():
                self.web_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.web_icon_label.setText("WB")
                self.web_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.web_icon_label.setText("WB")
            self.web_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")

        self.web_start_btn = QPushButton("Start")
        self.web_start_btn.setFixedSize(60, 30)
        self.web_start_btn.clicked.connect(self.start_webserver)

        self.web_stop_btn = QPushButton("Stop")
        self.web_stop_btn.setFixedSize(60, 30)
        self.web_stop_btn.clicked.connect(self.stop_webserver)
        self.web_stop_btn.setEnabled(False)

        self.web_path_btn = QPushButton("Path")
        self.web_path_btn.setFixedSize(60, 30)
        self.web_path_btn.clicked.connect(self.select_webserver_path)

        self.web_logs_btn = QPushButton("Log")
        self.web_logs_btn.setFixedSize(60, 30)
        self.web_logs_btn.clicked.connect(self.open_web_logs)

        self.web_config_btn = QPushButton("Config")
        self.web_config_btn.setFixedSize(60, 30)
        self.web_config_btn.clicked.connect(self.open_web_config)

        self.web_folder_btn = QPushButton()
        self.web_folder_btn.setFixedSize(40, 30)
        self.web_folder_btn.setToolTip("Open Webserver folder")
        self.web_folder_btn.clicked.connect(self.open_web_folder)
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.web_folder_btn.setIcon(QIcon(folder_icon_path))
                self.web_folder_btn.setIconSize(QSize(18, 18))
            else:
                self.web_folder_btn.setText("F")
                self.web_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.web_folder_btn.setText("F")
            self.web_folder_btn.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")

        self.web_status_container = QWidget()
        self.web_status_container.setFixedSize(50, 30)
        self.web_status_container.setLayout(QHBoxLayout())
        self.web_status_container.layout().setContentsMargins(0, 0, 0, 0)
        self.web_status_container.layout().setSpacing(0)
        self.web_status_container.layout().addStretch()

        self.web_status_led = QPushButton()
        self.web_status_led.setFixedSize(16, 16)
        self.web_status_led.setEnabled(False)
        self.web_status_led.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; border-radius: 8px; }")
        self.web_status_container.layout().addWidget(self.web_status_led)
        self.web_status_container.layout().addStretch()

        self.web_timer_container = QWidget()
        self.web_timer_container.setFixedSize(40, 30)

        self.web_countdown_btn = QPushButton("")
        self.web_countdown_btn.setFixedSize(40, 28)
        self.web_countdown_btn.setEnabled(False)
        self.web_countdown_btn.setStyleSheet("QPushButton:disabled { background-color: #f0f0f0; border: 1px solid #c0c0c0; color: #666666; }")
        self.web_countdown_btn.setFont(countdown_font)

        self.web_timer_container.setLayout(QVBoxLayout())
        self.web_timer_container.layout().setContentsMargins(0, 0, 0, 0)
        self.web_timer_container.layout().setSpacing(0)
        self.web_timer_container.layout().addWidget(self.web_countdown_btn)
        
        # Webserver Info Icon
        self.web_info_icon = QLabel()
        self.web_info_icon.setFixedSize(16, 16)
        self.web_info_icon.setToolTip("Push Path and choose httpd.exe from your webserver Apache folder.\nConfig will open the httpd.conf from your Apache/conf folder and Logs will open the folder Apache/Logs.\nTimer for opening Apache server is set to 15 sec.\nFolder Icon will open the selected path.\nUse Start/Stop to Open/Close application.")
        self.web_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Load info icon for Webserver
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.web_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.web_info_icon.setText("i")
                self.web_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                    }
                """)
        else:
            self.web_info_icon.setText("i")
            self.web_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                }
            """)
        
        self.web_info_icon.setAlignment(Qt.AlignCenter)
        
        web_layout.addWidget(self.web_label)
        web_layout.addWidget(self.web_icon_label)
        web_layout.addWidget(self.web_start_btn)
        web_layout.addWidget(self.web_stop_btn)
        web_layout.addWidget(self.web_path_btn)
        web_layout.addWidget(self.web_logs_btn)
        web_layout.addWidget(self.web_config_btn)
        web_layout.addWidget(self.web_folder_btn)
        web_layout.addWidget(self.web_status_container)
        web_layout.addWidget(self.web_timer_container)
        
        # Add spacing before info icon
        web_spacer = QLabel()
        web_spacer.setFixedSize(10, 30)  # Small spacer between counter and info icon
        
        web_layout.addWidget(web_spacer)
        web_layout.addWidget(self.web_info_icon)
        web_layout.addStretch()

        main_layout.addLayout(web_layout)
        
        # 10px spacer after webserver line
        spacer_10px = QLabel()
        spacer_10px.setFixedHeight(10)
        main_layout.addWidget(spacer_10px)
        
        # 10px spacer before editor header
        spacer_10px_2 = QLabel()
        spacer_10px_2.setFixedHeight(10)
        main_layout.addWidget(spacer_10px_2)
        
        # Editor Tools Header Row
        editor_header_layout = QHBoxLayout()
        editor_header_layout.setContentsMargins(0, 0, 0, 0)
        editor_header_layout.setSpacing(0)
        
        # Center the header text horizontally in the window
        editor_header_layout.addStretch()
        
        # Main Editing Tools header text
        editor_header_text = QLabel("Main Editing Tools")
        editor_header_text.setAlignment(Qt.AlignCenter)
        editor_header_font = QFont()
        editor_header_font.setBold(True)
        editor_header_font.setPointSize(10)
        editor_header_text.setFont(editor_header_font)
        editor_header_text.setStyleSheet("color: #666666;")
        editor_header_layout.addWidget(editor_header_text)
        
        editor_header_layout.addStretch()
        
        # Editor Tools Row
        editor_layout = QHBoxLayout()
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)
        
        # Editor label
        self.editor_label = GradientLabel("Editors")
        self.editor_label.setFont(font)
        self.editor_label.setAlignment(Qt.AlignVCenter)
        self.editor_label.setFixedWidth(100)
        
        # Editor icon
        self.editor_icon_label = QLabel()
        self.editor_icon_label.setFixedSize(32, 32)
        
        # Load edit icon
        edit_icon_path = os.path.join(script_dir, "icons", "edit_icon.png")
        if os.path.isfile(edit_icon_path):
            pixmap = QPixmap(edit_icon_path)
            if not pixmap.isNull():
                self.editor_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.editor_icon_label.setText("ED")
                self.editor_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.editor_icon_label.setText("ED")
            self.editor_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.editor_icon_label.setAlignment(Qt.AlignCenter)
        
        # Heidi button
        self.heidi_btn = QPushButton("Heidi")
        self.heidi_btn.setFixedSize(50, 30)
        self.heidi_btn.clicked.connect(self.open_heidi)
        self.heidi_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.heidi_btn.customContextMenuRequested.connect(self.show_heidi_context_menu)
        
        # Keira button
        self.keira_btn = QPushButton("Keira")
        self.keira_btn.setFixedSize(50, 30)
        self.keira_btn.clicked.connect(self.open_keira)
        self.keira_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.keira_btn.customContextMenuRequested.connect(self.show_keira_context_menu)
        
        # MPQ Editor button
        self.mpq_btn = QPushButton("Mpq Ed")
        self.mpq_btn.setFixedSize(64, 30)
        self.mpq_btn.clicked.connect(self.open_mpq_editor)
        self.mpq_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.mpq_btn.customContextMenuRequested.connect(self.show_mpq_context_menu)
        
        # WDBX Editor button
        self.wdbx_btn = QPushButton("Wdbx Ed")
        self.wdbx_btn.setFixedSize(64, 30)
        self.wdbx_btn.clicked.connect(self.open_wdbx_editor)
        self.wdbx_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.wdbx_btn.customContextMenuRequested.connect(self.show_wdbx_context_menu)
        
        # Spell Editor button
        self.spell_btn = QPushButton("Spell Ed")
        self.spell_btn.setFixedSize(64, 30)
        self.spell_btn.clicked.connect(self.open_spell_editor)
        self.spell_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.spell_btn.customContextMenuRequested.connect(self.show_spell_context_menu)
        
        # Np++ button
        self.npp_btn = QPushButton("Np++")
        self.npp_btn.setFixedSize(50, 30)
        self.npp_btn.clicked.connect(self.open_notepad_plus)
        self.npp_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.npp_btn.customContextMenuRequested.connect(self.show_npp_context_menu)
        
        # Trinity Creator button
        self.trinity_btn = QPushButton("Trinity Creator")
        self.trinity_btn.setFixedSize(90, 30)
        self.trinity_btn.clicked.connect(self.open_trinity_creator)
        self.trinity_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.trinity_btn.customContextMenuRequested.connect(self.show_trinity_context_menu)
        
        # Editor Info Icon
        self.editor_info_icon = QLabel()
        self.editor_info_icon.setFixedSize(16, 16)
        self.editor_info_icon.setToolTip("Right click to select editor app path.\nAfter that left click to open app.\nRight click again to change the actual path.")
        self.editor_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
                max-width: 300px;
                white-space: normal;
            }
        """)
        
        # Load info icon for Editor
        info_icon_path = os.path.join(script_dir, "icons", "info_icon.png")
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.editor_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.editor_info_icon.setText("i")
                self.editor_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                        max-width: 300px;
                        white-space: normal;
                    }
                """)
        else:
            self.editor_info_icon.setText("i")
            self.editor_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                    max-width: 300px;
                    white-space: normal;
                }
            """)
        
        self.editor_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add editor widgets to layout
        editor_layout.addWidget(self.editor_label)
        editor_layout.addWidget(self.editor_icon_label)
        editor_layout.addWidget(self.heidi_btn)
        editor_layout.addWidget(self.keira_btn)
        editor_layout.addWidget(self.mpq_btn)
        editor_layout.addWidget(self.wdbx_btn)
        editor_layout.addWidget(self.spell_btn)
        editor_layout.addWidget(self.npp_btn)
        editor_layout.addWidget(self.trinity_btn)
        
        # Add spacing before info icon
        editor_spacer = QLabel()
        editor_spacer.setFixedSize(10, 30)  # Small spacer between buttons and info icon
        
        editor_layout.addWidget(editor_spacer)
        editor_layout.addWidget(self.editor_info_icon)
        editor_layout.addStretch()
        
        # Add editor sections to main layout
        main_layout.addLayout(editor_header_layout)
        main_layout.addLayout(editor_layout)
        
        # 10px spacer between editor rows
        editor_row_spacer = QLabel()
        editor_row_spacer.setFixedHeight(10)
        main_layout.addWidget(editor_row_spacer)
        
        # Other Tools Header Row
        other_tools_header_layout = QHBoxLayout()
        other_tools_header_layout.setContentsMargins(0, 0, 0, 0)
        other_tools_header_layout.setSpacing(0)
        
        # Center the header text horizontally in the window
        other_tools_header_layout.addStretch()
        
        # Other Tools header text
        other_tools_header_text = QLabel("Other tools")
        other_tools_header_text.setAlignment(Qt.AlignCenter)
        other_tools_header_text.setFont(editor_header_font)
        other_tools_header_text.setStyleSheet("color: #666666;")
        other_tools_header_layout.addWidget(other_tools_header_text)
        
        other_tools_header_layout.addStretch()
        
        # Other Editors Row
        other_editor_layout = QHBoxLayout()
        other_editor_layout.setContentsMargins(0, 0, 0, 0)
        other_editor_layout.setSpacing(0)
        
        # Others label
        self.others_label = GradientLabel("Others")
        self.others_label.setFont(font)
        self.others_label.setAlignment(Qt.AlignVCenter)
        self.others_label.setFixedWidth(100)
        
        # Others icon
        self.others_icon_label = QLabel()
        self.others_icon_label.setFixedSize(32, 32)
        
        # Load edit_icon2
        edit_icon2_path = os.path.join(script_dir, "icons", "edit_icon2.png")
        if os.path.isfile(edit_icon2_path):
            pixmap = QPixmap(edit_icon2_path)
            if not pixmap.isNull():
                self.others_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.others_icon_label.setText("OT")
                self.others_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.others_icon_label.setText("OT")
            self.others_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.others_icon_label.setAlignment(Qt.AlignCenter)
        
        # Other Editor buttons (5 buttons, total 432px to match first row total)
        self.other_editor1_btn = QPushButton("Your app")
        self.other_editor1_btn.setFixedSize(86, 30)
        self.other_editor1_btn.clicked.connect(self.open_other_editor1)
        self.other_editor1_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.other_editor1_btn.customContextMenuRequested.connect(self.show_other_editor1_context_menu)
        
        self.other_editor2_btn = QPushButton("Your app")
        self.other_editor2_btn.setFixedSize(86, 30)
        self.other_editor2_btn.clicked.connect(self.open_other_editor2)
        self.other_editor2_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.other_editor2_btn.customContextMenuRequested.connect(self.show_other_editor2_context_menu)
        
        self.other_editor3_btn = QPushButton("Your app")
        self.other_editor3_btn.setFixedSize(86, 30)
        self.other_editor3_btn.clicked.connect(self.open_other_editor3)
        self.other_editor3_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.other_editor3_btn.customContextMenuRequested.connect(self.show_other_editor3_context_menu)
        
        self.other_editor4_btn = QPushButton("Your app")
        self.other_editor4_btn.setFixedSize(86, 30)
        self.other_editor4_btn.clicked.connect(self.open_other_editor4)
        self.other_editor4_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.other_editor4_btn.customContextMenuRequested.connect(self.show_other_editor4_context_menu)
        
        self.other_editor5_btn = QPushButton("Your app")
        self.other_editor5_btn.setFixedSize(88, 30)
        self.other_editor5_btn.clicked.connect(self.open_other_editor5)
        self.other_editor5_btn.setContextMenuPolicy(Qt.CustomContextMenu)
        self.other_editor5_btn.customContextMenuRequested.connect(self.show_other_editor5_context_menu)
        
        # Others Info Icon
        self.others_info_icon = QLabel()
        self.others_info_icon.setFixedSize(16, 16)
        self.others_info_icon.setToolTip("Right click to select the app path for other desired apps except the predefined ones.\nAfter that left click to open app.\nRight click again to change the actual path.")
        self.others_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
                max-width: 300px;
                white-space: normal;
            }
        """)
        
        # Load info icon for Others
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.others_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.others_info_icon.setText("i")
                self.others_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                        max-width: 300px;
                        white-space: normal;
                    }
                """)
        else:
            self.others_info_icon.setText("i")
            self.others_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                    max-width: 300px;
                    white-space: normal;
                }
            """)
        
        self.others_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add other editor widgets to layout
        other_editor_layout.addWidget(self.others_label)
        other_editor_layout.addWidget(self.others_icon_label)
        other_editor_layout.addWidget(self.other_editor1_btn)
        other_editor_layout.addWidget(self.other_editor2_btn)
        other_editor_layout.addWidget(self.other_editor3_btn)
        other_editor_layout.addWidget(self.other_editor4_btn)
        other_editor_layout.addWidget(self.other_editor5_btn)
        
        # Add spacing before info icon
        others_spacer = QLabel()
        others_spacer.setFixedSize(10, 30)  # Small spacer between buttons and info icon
        
        other_editor_layout.addWidget(others_spacer)
        other_editor_layout.addWidget(self.others_info_icon)
        other_editor_layout.addStretch()
        
        # Add other tools header and other editor row to main layout
        main_layout.addLayout(other_tools_header_layout)
        main_layout.addLayout(other_editor_layout)
        
        # 10px spacer between editor rows
        editor_management_spacer = QLabel()
        editor_management_spacer.setFixedHeight(10)
        main_layout.addWidget(editor_management_spacer)
        
        # Server Management Header Row
        management_header_layout = QHBoxLayout()
        management_header_layout.setContentsMargins(0, 0, 0, 0)
        management_header_layout.setSpacing(0)
        
        # Center the header text horizontally in the window
        management_header_layout.addStretch()
        
        # Server Management header text
        management_header_text = QLabel("Server management")
        management_header_text.setAlignment(Qt.AlignCenter)
        management_header_text.setFont(editor_header_font)
        management_header_text.setStyleSheet("color: #666666;")
        management_header_layout.addWidget(management_header_text)
        
        management_header_layout.addStretch()
        
        # Server Management Row
        management_layout = QHBoxLayout()
        management_layout.setContentsMargins(0, 0, 0, 0)
        management_layout.setSpacing(0)
        
        # Management label
        self.management_label = GradientLabel("Utils")
        self.management_label.setFont(font)
        self.management_label.setAlignment(Qt.AlignVCenter)
        self.management_label.setFixedWidth(100)
        
        # Management icon
        self.management_icon_label = QLabel()
        self.management_icon_label.setFixedSize(32, 32)
        
        # Load management icon
        management_icon_path = os.path.join(script_dir, "icons", "management_icon.png")
        if os.path.isfile(management_icon_path):
            pixmap = QPixmap(management_icon_path)
            if not pixmap.isNull():
                self.management_icon_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.management_icon_label.setText("MG")
                self.management_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.management_icon_label.setText("MG")
            self.management_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.management_icon_label.setAlignment(Qt.AlignCenter)
        
        # Management buttons (5 buttons, each 86px to fit within the row width)
        self.account_btn = QPushButton("Account")
        self.account_btn.setFixedSize(86, 30)
        self.account_btn.clicked.connect(self.open_account_page)
        
        self.db_backup_btn = QPushButton("DB backup")
        self.db_backup_btn.setFixedSize(86, 30)
        self.db_backup_btn.clicked.connect(self.db_backup_action)
        
        self.db_restore_btn = QPushButton("DB restore")
        self.db_restore_btn.setFixedSize(86, 30)
        self.db_restore_btn.clicked.connect(self.db_restore_action)
        
        self.ch_backup_btn = QPushButton("CH backup")
        self.ch_backup_btn.setFixedSize(86, 30)
        self.ch_backup_btn.clicked.connect(self.ch_backup_action)
        
        self.ch_restore_btn = QPushButton("CH restore")
        self.ch_restore_btn.setFixedSize(86, 30)
        self.ch_restore_btn.clicked.connect(self.ch_restore_action)
        
        # Management Info Icon
        self.management_info_icon = QLabel()
        self.management_info_icon.setFixedSize(16, 16)
        self.management_info_icon.setToolTip("Click account for account creation,\nDB backup for database backup and DB restore for database restore.\nIn the same way use CH backup and CH restore.")
        self.management_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
                max-width: 300px;
                white-space: normal;
            }
        """)
        
        # Load info icon for Management
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.management_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.management_info_icon.setText("i")
                self.management_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                        max-width: 300px;
                        white-space: normal;
                    }
                """)
        else:
            self.management_info_icon.setText("i")
            self.management_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                    max-width: 300px;
                    white-space: normal;
                }
            """)
        
        self.management_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add management widgets to layout
        management_layout.addWidget(self.management_label)
        management_layout.addWidget(self.management_icon_label)
        management_layout.addWidget(self.account_btn)
        management_layout.addWidget(self.db_backup_btn)
        management_layout.addWidget(self.db_restore_btn)
        management_layout.addWidget(self.ch_backup_btn)
        management_layout.addWidget(self.ch_restore_btn)
        
        # Add spacing before info icon
        management_spacer = QLabel()
        management_spacer.setFixedSize(10, 30)  # Small spacer between buttons and info icon
        
        management_layout.addWidget(management_spacer)
        management_layout.addWidget(self.management_info_icon)
        management_layout.addStretch()
        
        # Add management header and management row to main layout
        main_layout.addLayout(management_header_layout)
        main_layout.addLayout(management_layout)
        
        # 10px spacer between management and work folders
        management_folders_spacer = QLabel()
        management_folders_spacer.setFixedHeight(10)
        main_layout.addWidget(management_folders_spacer)
        
        # Work Folders Header Row
        work_folders_header_layout = QHBoxLayout()
        work_folders_header_layout.setContentsMargins(0, 0, 0, 0)
        work_folders_header_layout.setSpacing(0)
        
        # Center the header text horizontally in the window
        work_folders_header_layout.addStretch()
        
        # Work Folders header text
        work_folders_header_text = QLabel("Work folders")
        work_folders_header_text.setAlignment(Qt.AlignCenter)
        work_folders_header_text.setFont(editor_header_font)
        work_folders_header_text.setStyleSheet("color: #666666;")
        work_folders_header_layout.addWidget(work_folders_header_text)
        
        work_folders_header_layout.addStretch()
        
        # Work Folders Row
        work_folders_layout = QHBoxLayout()
        work_folders_layout.setContentsMargins(0, 0, 0, 0)
        work_folders_layout.setSpacing(0)
        
        # Folders label
        self.folders_label = GradientLabel("Folders")
        self.folders_label.setFont(font)
        self.folders_label.setAlignment(Qt.AlignVCenter)
        self.folders_label.setFixedWidth(100)
        
        # Folders icon
        self.folders_icon_label = QLabel()
        self.folders_icon_label.setFixedSize(27, 27)
        
        # Load folder icon
        folder_icon_path = os.path.join(script_dir, "icons", "folder_icon.png")
        if os.path.isfile(folder_icon_path):
            pixmap = QPixmap(folder_icon_path)
            if not pixmap.isNull():
                self.folders_icon_label.setPixmap(pixmap.scaled(27, 27, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.folders_icon_label.setText("FD")
                self.folders_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            self.folders_icon_label.setText("FD")
            self.folders_icon_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        self.folders_icon_label.setAlignment(Qt.AlignCenter)
        
        # Work folder buttons (6 buttons, each 71px to align with other rows)
        self.lua_scripts_btn = QPushButton("lua_scripts")
        self.lua_scripts_btn.setFixedSize(71, 30)
        self.lua_scripts_btn.clicked.connect(self.open_lua_scripts_folder)
        
        self.modules_btn = QPushButton("modules")
        self.modules_btn.setFixedSize(71, 30)
        self.modules_btn.clicked.connect(self.open_modules_folder)
        
        self.dbc_btn = QPushButton("DBC")
        self.dbc_btn.setFixedSize(71, 30)
        self.dbc_btn.clicked.connect(self.open_dbc_folder)
        
        self.backup_btn = QPushButton("Backup")
        self.backup_btn.setFixedSize(71, 30)
        self.backup_btn.clicked.connect(self.open_backup_folder)
        
        self.client_data_btn = QPushButton("Data")
        self.client_data_btn.setFixedSize(71, 30)
        self.client_data_btn.clicked.connect(self.open_client_data_folder)
        
        self.addons_btn = QPushButton("Addons")
        self.addons_btn.setFixedSize(75, 30)
        self.addons_btn.clicked.connect(self.open_addons_folder)
        
        # Folders Info Icon
        self.folders_info_icon = QLabel()
        self.folders_info_icon.setFixedSize(16, 16)
        self.folders_info_icon.setToolTip("Server and client folder will be set\naccording to the paths selected in the previous sections")
        self.folders_info_icon.setStyleSheet("""
            QLabel {
                background-color: transparent;
            }
            QLabel::tooltip {
                background-color: #fff8dc;
                color: #856404;
                border: 1px solid #ffeaa7;
                border-radius: 4px;
                padding: 4px;
                max-width: 300px;
                white-space: normal;
            }
        """)
        
        # Load info icon for Folders
        if os.path.isfile(info_icon_path):
            pixmap = QPixmap(info_icon_path)
            if not pixmap.isNull():
                self.folders_info_icon.setPixmap(pixmap.scaled(16, 16, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.folders_info_icon.setText("i")
                self.folders_info_icon.setStyleSheet("""
                    QLabel {
                        background-color: transparent;
                        color: #666666;
                        font-weight: bold;
                        font-size: 12px;
                    }
                    QLabel::tooltip {
                        background-color: #fff8dc;
                        color: #856404;
                        border: 1px solid #ffeaa7;
                        border-radius: 4px;
                        padding: 4px;
                        max-width: 300px;
                        white-space: normal;
                    }
                """)
        else:
            self.folders_info_icon.setText("i")
            self.folders_info_icon.setStyleSheet("""
                QLabel {
                    background-color: transparent;
                    color: #666666;
                    font-weight: bold;
                    font-size: 12px;
                }
                QLabel::tooltip {
                    background-color: #fff8dc;
                    color: #856404;
                    border: 1px solid #ffeaa7;
                    border-radius: 4px;
                    padding: 4px;
                    max-width: 300px;
                    white-space: normal;
                }
            """)
        
        self.folders_info_icon.setAlignment(Qt.AlignCenter)
        
        # Add work folders widgets to layout
        work_folders_layout.addWidget(self.folders_label)
        work_folders_layout.addWidget(self.folders_icon_label)
        
        # Add spacer to align lua_scripts button with Account button
        alignment_spacer = QLabel()
        alignment_spacer.setFixedSize(5, 30)  # 5px spacer to align with Account button
        work_folders_layout.addWidget(alignment_spacer)
        
        work_folders_layout.addWidget(self.lua_scripts_btn)
        work_folders_layout.addWidget(self.modules_btn)
        work_folders_layout.addWidget(self.dbc_btn)
        work_folders_layout.addWidget(self.backup_btn)
        work_folders_layout.addWidget(self.client_data_btn)
        work_folders_layout.addWidget(self.addons_btn)
        
        # Add spacing before info icon
        folders_spacer = QLabel()
        folders_spacer.setFixedSize(10, 30)  # Small spacer between buttons and info icon
        
        work_folders_layout.addWidget(folders_spacer)
        work_folders_layout.addWidget(self.folders_info_icon)
        work_folders_layout.addStretch()
        
        # Add work folders header and work folders row to main layout
        main_layout.addLayout(work_folders_header_layout)
        main_layout.addLayout(work_folders_layout)
        
        # 20px spacer at bottom
        bottom_spacer = QLabel()
        bottom_spacer.setFixedHeight(20)
        main_layout.addWidget(bottom_spacer)
        
        # Credit text in lower right corner
        credit_layout = QHBoxLayout()
        credit_layout.setContentsMargins(0, 0, 2, 2)  # 2px left, 2px up
        credit_layout.addStretch()  # Push text to the right
        
        credit_label = QLabel("Created by F@bagun")
        credit_font = QFont()
        credit_font.setPointSize(8)
        credit_label.setFont(credit_font)
        credit_label.setStyleSheet("color: #888888;")  # Subtle grey color
        credit_layout.addWidget(credit_label)
        
        main_layout.addLayout(credit_layout)
        
        # Set random background image using palette (optimized)
        import random
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # List of possible background files
        background_files = ["background.png", "background1.png", "background2.png", "background3.png", "background4.png"]
        
        # Randomly select a background file
        selected_background = random.choice(background_files)
        background_path = os.path.join(script_dir, selected_background)
        
        if os.path.isfile(background_path):
            try:
                pixmap = QPixmap(background_path)
                if not pixmap.isNull():
                    # Scale the pixmap to fit the window exactly
                    scaled_pixmap = pixmap.scaled(700, 460, Qt.IgnoreAspectRatio, Qt.FastTransformation)
                    # Create a palette with the background image
                    palette = self.palette()
                    palette.setBrush(self.backgroundRole(), QBrush(scaled_pixmap))
                    self.setPalette(palette)
                    self.setAutoFillBackground(True)
                    # Clear original pixmap to free memory
                    pixmap = None
                else:
                    self.setStyleSheet("background-color: #f0f0f0;")
            except Exception:
                self.setStyleSheet("background-color: #f0f0f0;")
        else:
            self.setStyleSheet("background-color: #f0f0f0;")
        
        # Set the main layout directly
        self.setLayout(main_layout)
        
        # Initialize autorestart checkbox state
        self.autorestart_checkbox.setChecked(self.autorestart_enabled)

    def update_other_editor_button_texts(self):
        """Update the text of other editor buttons from saved text variables"""
        if hasattr(self, 'other_editor1_btn') and self.other_editor1_text:
            self.other_editor1_btn.setText(self.other_editor1_text)
        if hasattr(self, 'other_editor2_btn') and self.other_editor2_text:
            self.other_editor2_btn.setText(self.other_editor2_text)
        if hasattr(self, 'other_editor3_btn') and self.other_editor3_text:
            self.other_editor3_btn.setText(self.other_editor3_text)
        if hasattr(self, 'other_editor4_btn') and self.other_editor4_text:
            self.other_editor4_btn.setText(self.other_editor4_text)
        if hasattr(self, 'other_editor5_btn') and self.other_editor5_text:
            self.other_editor5_btn.setText(self.other_editor5_text)

    def set_status_led(self, status):
        """Set LED color based on status: 'stopped', 'starting', 'running'"""
        if status == "running":
            self.status_led.setStyleSheet("QPushButton:disabled { background-color: green; border: 1px solid #c0c0c0; border-radius: 8px; }")
        elif status == "starting":
            self.status_led.setStyleSheet("QPushButton:disabled { background-color: yellow; border: 1px solid #c0c0c0; border-radius: 8px; }")
        else:  # stopped
            self.status_led.setStyleSheet("QPushButton:disabled { background-color: red; border: 1px solid #c0c0c0; border-radius: 8px; }")

    def set_client_status_led(self, status):
        if status == "running":
            self.client_status_led.setStyleSheet("QPushButton:disabled { background-color: green; border: 1px solid #c0c0c0; border-radius: 8px; }")
        elif status == "starting":
            self.client_status_led.setStyleSheet("QPushButton:disabled { background-color: yellow; border: 1px solid #c0c0c0; border-radius: 8px; }")
        else:
            self.client_status_led.setStyleSheet("QPushButton:disabled { background-color: red; border: 1px solid #c0c0c0; border-radius: 8px; }")

    def load_config(self):
        """Load MySQL and AuthServer paths from config file"""
        if os.path.isfile(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.mysql_path = data.get("mysql_path", "")
                    self.auth_path = data.get("auth_path", "")
                    self.world_path = data.get("world_path", "")
                    self.client_path = data.get("client_path", "")
                    self.web_path = data.get("web_path", "")
                    self.autorestart_enabled = data.get("autorestart_enabled", False)
                    
                    # Load editor paths
                    self.heidi_path = data.get("heidi_path", "")
                    self.keira_path = data.get("keira_path", "")
                    self.mpq_editor_path = data.get("mpq_editor_path", "")
                    self.wdbx_editor_path = data.get("wdbx_editor_path", "")
                    self.spell_editor_path = data.get("spell_editor_path", "")
                    self.notepad_plus_path = data.get("notepad_plus_path", "")
                    self.trinity_creator_path = data.get("trinity_creator_path", "")
                    
                    # Load other editor paths
                    self.other_editor1_path = data.get("other_editor1_path", "")
                    self.other_editor2_path = data.get("other_editor2_path", "")
                    self.other_editor3_path = data.get("other_editor3_path", "")
                    self.other_editor4_path = data.get("other_editor4_path", "")
                    self.other_editor5_path = data.get("other_editor5_path", "")
                    
                    # Load other editor button texts
                    self.other_editor1_text = data.get("other_editor1_text", "Your app")
                    self.other_editor2_text = data.get("other_editor2_text", "Your app")
                    self.other_editor3_text = data.get("other_editor3_text", "Your app")
                    self.other_editor4_text = data.get("other_editor4_text", "Your app")
                    self.other_editor5_text = data.get("other_editor5_text", "Your app")
                    
                    # Set checkbox state
                    if hasattr(self, 'autorestart_checkbox'):
                        self.autorestart_checkbox.setChecked(self.autorestart_enabled)
                    
                    # Update other editor button texts if texts are loaded
                    if hasattr(self, 'other_editor1_btn') and self.other_editor1_text:
                        self.other_editor1_btn.setText(self.other_editor1_text)
                    if hasattr(self, 'other_editor2_btn') and self.other_editor2_text:
                        self.other_editor2_btn.setText(self.other_editor2_text)
                    if hasattr(self, 'other_editor3_btn') and self.other_editor3_text:
                        self.other_editor3_btn.setText(self.other_editor3_text)
                    if hasattr(self, 'other_editor4_btn') and self.other_editor4_text:
                        self.other_editor4_btn.setText(self.other_editor4_text)
                    if hasattr(self, 'other_editor5_btn') and self.other_editor5_text:
                        self.other_editor5_btn.setText(self.other_editor5_text)
            except Exception:
                self.mysql_path = ""
                self.auth_path = ""
                self.world_path = ""
                self.client_path = ""
                self.web_path = ""
                self.autorestart_enabled = False
                
                # Reset editor paths
                self.heidi_path = ""
                self.keira_path = ""
                self.mpq_editor_path = ""
                self.wdbx_editor_path = ""
                self.spell_editor_path = ""
                self.notepad_plus_path = ""
                self.trinity_creator_path = ""
        else:
            self.mysql_path = ""
            self.auth_path = ""
            self.world_path = ""
            self.client_path = ""
            self.web_path = ""
            self.autorestart_enabled = False
            
            # Reset editor paths
            self.heidi_path = ""
            self.keira_path = ""
            self.mpq_editor_path = ""
            self.wdbx_editor_path = ""
            self.spell_editor_path = ""
            self.notepad_plus_path = ""
            self.trinity_creator_path = ""
    
    def save_config(self):
        """Save MySQL and AuthServer paths to config file"""
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({
                    "mysql_path": self.mysql_path,
                    "auth_path": self.auth_path,
                    "world_path": self.world_path,
                    "client_path": self.client_path,
                    "web_path": self.web_path,
                    "autorestart_enabled": self.autorestart_enabled,
                    "heidi_path": self.heidi_path,
                    "keira_path": self.keira_path,
                    "mpq_editor_path": self.mpq_editor_path,
                    "wdbx_editor_path": self.wdbx_editor_path,
                    "spell_editor_path": self.spell_editor_path,
                    "notepad_plus_path": self.notepad_plus_path,
                    "trinity_creator_path": self.trinity_creator_path,
                    "other_editor1_path": self.other_editor1_path,
                    "other_editor2_path": self.other_editor2_path,
                    "other_editor3_path": self.other_editor3_path,
                    "other_editor4_path": self.other_editor4_path,
                    "other_editor5_path": self.other_editor5_path,
                    "other_editor1_text": self.other_editor1_text,
                    "other_editor2_text": self.other_editor2_text,
                    "other_editor3_text": self.other_editor3_text,
                    "other_editor4_text": self.other_editor4_text,
                    "other_editor5_text": self.other_editor5_text
                }, f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {str(e)}")

    def select_mysql_path(self):
        """Open file dialog to select MySQL executable"""
        if self.mysql_path and os.path.isfile(self.mysql_path):
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select MySQL Executable", 
            "", 
            "Executable files (*.exe);;All files (*.*)"
        )
        if path:
            self.mysql_path = path
            self.save_config()
            QMessageBox.information(self, "Success", "MySQL path saved successfully!")
    
    def select_authserver_path(self):
        """Open file dialog to select AuthServer executable"""
        if self.auth_path and os.path.isfile(self.auth_path):
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select AuthServer Executable", 
            "", 
            "Executable files (*.exe);;All files (*.*)"
        )
        if path:
            self.auth_path = path
            self.save_config()
            QMessageBox.information(self, "Success", "AuthServer path saved successfully!")

    def select_worldserver_path(self):
        """Open file dialog to select WorldServer executable"""
        if self.world_path and os.path.isfile(self.world_path):
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select WorldServer Executable", 
            "", 
            "Executable files (*.exe);;All files (*.*)"
        )
        if path:
            self.world_path = path
            self.save_config()
            QMessageBox.information(self, "Success", "WorldServer path saved successfully!")

    def select_webserver_path(self):
        """Open file dialog to select Webserver executable"""
        if self.web_path and os.path.isfile(self.web_path):
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Webserver Executable",
            "",
            "Executable files (*.exe);;All files (*.*)"
        )
        if path:
            self.web_path = path
            self.save_config()
            QMessageBox.information(self, "Success", "Webserver path saved successfully!")

    def select_client_path(self):
        """Open file dialog to select Client executable"""
        if self.client_path and os.path.isfile(self.client_path):
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return
        
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Client Executable",
            "",
            "Executable files (*.exe);;All files (*.*)"
        )
        if path:
            self.client_path = path
            self.save_config()
            QMessageBox.information(self, "Success", "Client path saved successfully!")

    def start_mysql(self):
        """Start MySQL server"""
        if not self.mysql_path or not os.path.isfile(self.mysql_path):
            QMessageBox.warning(self, "Error", "Please select a valid MySQL executable path first!")
            return
        
        if self.process_thread and self.process_thread.isRunning():
            QMessageBox.information(self, "Info", "MySQL is already running!")
            return
        
        try:
            # Set starting status
            self.is_starting = True
            self.set_status_led("starting")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(False)
            
            # Start process thread
            self.process_thread = MySQLProcessThread(self.mysql_path)
            self.process_thread.log_signal.connect(self.on_log_output)
            self.process_thread.finished.connect(self.on_process_finished)
            
            # Memory monitoring is handled by the main timer
            pass
            self.process_thread.start()
            
            # Start 10-second timer for starting status
            self.startup_timer = QTimer(self)
            self.startup_timer.timeout.connect(self.on_startup_timeout)
            self.startup_timer.start(10000)  # 10 seconds
            
            # Initialize countdown
            self.mysql_countdown_seconds = 10
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start MySQL: {str(e)}")
            self.set_status_led("stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def start_authserver(self):
        """Start AuthServer"""
        if not self.auth_path or not os.path.isfile(self.auth_path):
            QMessageBox.warning(self, "Error", "Please select a valid AuthServer executable path first!")
            return
        
        if self.auth_process_thread and self.auth_process_thread.isRunning():
            QMessageBox.information(self, "Info", "AuthServer is already running!")
            return
        
        try:
            # Set starting status
            self.auth_is_starting = True
            self.set_auth_status_led("starting")
            self.auth_start_btn.setEnabled(False)
            self.auth_stop_btn.setEnabled(False)
            
            # Start process thread
            self.auth_process_thread = AuthServerProcessThread(self.auth_path)
            self.auth_process_thread.log_signal.connect(self.on_auth_log_output)
            self.auth_process_thread.finished.connect(self.on_auth_process_finished)
            
            # Memory monitoring is handled by the main timer
            pass
            self.auth_process_thread.start()
            
            # Start 10-second timer for starting status
            self.auth_startup_timer = QTimer(self)
            self.auth_startup_timer.timeout.connect(self.on_auth_startup_timeout)
            self.auth_startup_timer.start(10000)  # 10 seconds
            
            # Initialize countdown
            self.auth_countdown_seconds = 10
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start AuthServer: {str(e)}")
            self.set_auth_status_led("stopped")
            self.auth_start_btn.setEnabled(True)
            self.auth_stop_btn.setEnabled(False)

    def start_worldserver(self):
        """Start WorldServer"""
        if not self.world_path or not os.path.isfile(self.world_path):
            QMessageBox.warning(self, "Error", "Please select a valid WorldServer executable path first!")
            return
        
        if self.world_process_thread and self.world_process_thread.isRunning():
            QMessageBox.information(self, "Info", "WorldServer is already running!")
            return
        
        try:
            # Set starting status
            self.world_is_starting = True
            self.set_world_status_led("starting")
            self.world_start_btn.setEnabled(False)
            self.world_stop_btn.setEnabled(False)
            
            # Start process thread
            self.world_process_thread = WorldServerProcessThread(self.world_path)
            self.world_process_thread.log_signal.connect(self.on_world_log_output)
            self.world_process_thread.finished.connect(self.on_world_process_finished)
            
            # Memory monitoring is handled by the main timer
            pass
            self.world_process_thread.start()
            
            # Start 10-second timer for starting status
            self.world_startup_timer = QTimer(self)
            self.world_startup_timer.timeout.connect(self.on_world_startup_timeout)
            self.world_startup_timer.start(120000)  # 120 seconds
            
            # Initialize countdown
            self.world_countdown_seconds = 120
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start WorldServer: {str(e)}")
            self.set_world_status_led("stopped")
            self.world_start_btn.setEnabled(True)
            self.world_stop_btn.setEnabled(False)

    def start_client(self):
        """Start Client"""
        if not self.client_path or not os.path.isfile(self.client_path):
            QMessageBox.warning(self, "Error", "Please select a valid Client executable path first!")
            return
        if self.client_process_thread and self.client_process_thread.isRunning():
            QMessageBox.information(self, "Info", "Client is already running!")
            return
        try:
            self.client_is_starting = True
            self.set_client_status_led("starting")
            self.client_start_btn.setEnabled(False)
            self.client_stop_btn.setEnabled(False)

            self.client_process_thread = ClientProcessThread(self.client_path)
            self.client_process_thread.log_signal.connect(lambda s: None)
            self.client_process_thread.finished.connect(self.on_client_process_finished)
            self.client_process_thread.start()

            # 15-second startup window
            self.client_startup_timer = QTimer(self)
            self.client_startup_timer.timeout.connect(self.on_client_startup_timeout)
            self.client_startup_timer.start(15000)
            self.client_countdown_seconds = 15
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start Client: {str(e)}")
            self.set_client_status_led("stopped")
            self.client_start_btn.setEnabled(True)
            self.client_stop_btn.setEnabled(False)

    def stop_mysql(self):
        """Stop MySQL server safely"""
        if not self.process_thread or not self.process_thread.isRunning():
            QMessageBox.information(self, "Info", "MySQL is not running!")
            return
        
        try:
            # Mark as manually stopped to prevent autorestart
            self.process_thread.was_manually_stopped = True
            
            # Stop the startup timer if running
            if self.startup_timer:
                self.startup_timer.stop()
                self.startup_timer = None
            
            # Stop the process
            self.process_thread.stop_process()
            self.process_thread.quit()
            self.process_thread.wait()
            
            self.set_status_led("stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.is_starting = False
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop MySQL: {str(e)}")
    
    def stop_authserver(self):
        """Stop AuthServer safely"""
        if not self.auth_process_thread or not self.auth_process_thread.isRunning():
            QMessageBox.information(self, "Info", "AuthServer is not running!")
            return
        
        try:
            # Mark as manually stopped to prevent autorestart
            self.auth_process_thread.was_manually_stopped = True
            
            # Stop the startup timer if running
            if self.auth_startup_timer:
                self.auth_startup_timer.stop()
                self.auth_startup_timer = None
            
            # Stop the process
            self.auth_process_thread.stop_process()
            self.auth_process_thread.quit()
            self.auth_process_thread.wait()
            
            self.set_auth_status_led("stopped")
            self.auth_start_btn.setEnabled(True)
            self.auth_stop_btn.setEnabled(False)
            self.auth_is_starting = False
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop AuthServer: {str(e)}")
    
    def stop_worldserver(self):
        """Stop WorldServer safely"""
        if not self.world_process_thread or not self.world_process_thread.isRunning():
            QMessageBox.information(self, "Info", "WorldServer is not running!")
            return
        
        try:
            # Mark as manually stopped to prevent autorestart
            self.world_process_thread.was_manually_stopped = True
            
            # Stop the startup timer if running
            if self.world_startup_timer:
                self.world_startup_timer.stop()
                self.world_startup_timer = None
            
            # Stop the process
            self.world_process_thread.stop_process()
            self.world_process_thread.quit()
            self.world_process_thread.wait()
            
            self.set_world_status_led("stopped")
            self.world_start_btn.setEnabled(True)
            self.world_stop_btn.setEnabled(False)
            self.world_is_starting = False
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop WorldServer: {str(e)}")

    def start_webserver(self):
        """Start Webserver"""
        if not self.web_path or not os.path.isfile(self.web_path):
            QMessageBox.warning(self, "Error", "Please select a valid Webserver executable path first!")
            return
        if hasattr(self, 'web_process_thread') and self.web_process_thread and self.web_process_thread.isRunning():
            QMessageBox.information(self, "Info", "Webserver is already running!")
            return
        try:
            self.web_is_starting = True
            self.set_web_status_led("starting")
            self.web_start_btn.setEnabled(False)
            self.web_stop_btn.setEnabled(False)

            self.web_process_thread = WebServerProcessThread(self.web_path)
            self.web_process_thread.log_signal.connect(lambda s: None)
            self.web_process_thread.finished.connect(self.on_web_process_finished)
            self.web_process_thread.start()

            # 10-second startup window
            self.web_startup_timer = QTimer(self)
            self.web_startup_timer.timeout.connect(self.on_web_startup_timeout)
            self.web_startup_timer.start(10000)
            self.web_countdown_seconds = 10
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start Webserver: {str(e)}")
            self.set_web_status_led("stopped")
            self.web_start_btn.setEnabled(True)
            self.web_stop_btn.setEnabled(False)

    def stop_webserver(self):
        """Stop Webserver safely"""
        try:
            if hasattr(self, 'web_startup_timer') and self.web_startup_timer:
                self.web_startup_timer.stop()
                self.web_startup_timer = None
            if hasattr(self, 'web_process_thread') and self.web_process_thread and self.web_process_thread.isRunning():
                try:
                    self.web_process_thread.stop_process()
                    self.web_process_thread.quit()
                    self.web_process_thread.wait()
                except Exception:
                    pass
            else:
                # Even if thread is not running, attempt to cleanup Apache processes
                try:
                    # Defensive: create a temporary thread instance to reuse cleanup logic
                    temp = WebServerProcessThread(self.web_path or "")
                    temp._cleanup_remaining_processes()
                except Exception:
                    pass
            self.set_web_status_led("stopped")
            self.web_start_btn.setEnabled(True)
            self.web_stop_btn.setEnabled(False)
            self.web_is_starting = False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop Webserver: {str(e)}")
    
    def stop_client(self):
        """Stop Client safely"""
        try:
            # Stop startup timer if active
            if hasattr(self, 'client_startup_timer') and self.client_startup_timer:
                self.client_startup_timer.stop()
                self.client_startup_timer = None

            # Attempt to stop the tracked process thread, if present
            if self.client_process_thread and self.client_process_thread.isRunning():
                try:
                    self.client_process_thread.stop_process()
                    self.client_process_thread.quit()
                    self.client_process_thread.wait()
                except Exception:
                    pass

            # Ensure wow.exe is terminated (client process name)
            if sys.platform == "win32":
                try:
                    subprocess.run(["taskkill", "/im", "wow.exe", "/f"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                except Exception:
                    pass

            # Update UI state
            self.set_client_status_led("stopped")
            self.client_start_btn.setEnabled(True)
            self.client_stop_btn.setEnabled(False)
            self.client_is_starting = False
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop Client: {str(e)}")

    def on_startup_timeout(self):
        """Called when 10-second startup timer expires"""
        self.startup_timer.stop()
        self.startup_timer = None
        self.is_starting = False
        self.mysql_countdown.setText("")
    
    def on_auth_startup_timeout(self):
        """Called when 10-second AuthServer startup timer expires"""
        self.auth_startup_timer.stop()
        self.auth_startup_timer = None
        self.auth_is_starting = False
        self.auth_countdown.setText("")
    
    def on_world_startup_timeout(self):
        """Called when 60-second WorldServer startup timer expires"""
        self.world_startup_timer.stop()
        self.world_startup_timer = None
        self.world_is_starting = False
        self.world_countdown.setText("")
    
    def on_client_startup_timeout(self):
        """Called when 15-second Client startup timer expires"""
        self.client_startup_timer.stop()
        self.client_startup_timer = None
        self.client_is_starting = False
        self.client_countdown.setText("")

    def on_web_startup_timeout(self):
        """Called when 10-second Webserver startup timer expires"""
        self.web_startup_timer.stop()
        self.web_startup_timer = None
        self.web_is_starting = False
        self.web_countdown_btn.setText("")
        
        # Automatically open localhost in default browser when counter finishes
        try:
            webbrowser.open('http://localhost')
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open localhost in browser: {str(e)}")
    
    def on_log_output(self, output):
        """Handle log output from MySQL process"""
        # This can be used for real-time logging if needed
        pass
    
    def on_auth_log_output(self, output):
        """Handle log output from AuthServer process"""
        # This can be used for real-time logging if needed
        pass
    
    def on_world_log_output(self, output):
        """Handle log output from WorldServer process"""
        # This can be used for real-time logging if needed
        pass
    
    def on_client_process_finished(self):
        """Called when Client process thread finishes"""
        self.set_client_status_led("stopped")
        self.client_start_btn.setEnabled(True)
        self.client_stop_btn.setEnabled(False)
        self.client_is_starting = False
    
    # Memory update handlers removed
    
    def on_process_finished(self):
        """Called when MySQL process thread finishes"""
        self.set_status_led("stopped")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.is_starting = False
        # Memory label removed
        
        # Trigger autorestart if enabled and process was running (not manually stopped)
        if self.autorestart_enabled and self.process_thread and not hasattr(self.process_thread, 'was_manually_stopped'):
            self.trigger_autorestart()
    
    def on_auth_process_finished(self):
        """Called when AuthServer process thread finishes"""
        self.set_auth_status_led("stopped")
        self.auth_start_btn.setEnabled(True)
        self.auth_stop_btn.setEnabled(False)
        self.auth_is_starting = False
        
        # Trigger autorestart if enabled and process was running (not manually stopped)
        if self.autorestart_enabled and self.auth_process_thread and not hasattr(self.auth_process_thread, 'was_manually_stopped'):
            self.trigger_autorestart()
        # Memory label removed
    
    def on_world_process_finished(self):
        """Called when WorldServer process thread finishes"""
        self.set_world_status_led("stopped")
        self.world_start_btn.setEnabled(True)
        self.world_stop_btn.setEnabled(False)
        self.world_is_starting = False
        
        # Trigger autorestart if enabled and process was running (not manually stopped)
        if self.autorestart_enabled and self.world_process_thread and not hasattr(self.world_process_thread, 'was_manually_stopped'):
            self.trigger_autorestart()
        # Memory label removed

    def on_web_process_finished(self):
        """Called when Webserver process thread finishes"""
        self.set_web_status_led("stopped")
        self.web_start_btn.setEnabled(True)
        self.web_stop_btn.setEnabled(False)
        self.web_is_starting = False

    def update_status(self):
        """Update status based on process state (optimized)"""
        # MySQL status
        if self.is_starting:
            self.set_status_led("starting")
        elif self.process_thread and self.process_thread.isRunning():
            self.set_status_led("running")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.set_status_led("stopped")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        
        # AuthServer status
        if self.auth_is_starting:
            self.set_auth_status_led("starting")
        elif self.auth_process_thread and self.auth_process_thread.isRunning():
            self.set_auth_status_led("running")
            self.auth_start_btn.setEnabled(False)
            self.auth_stop_btn.setEnabled(True)
        else:
            self.set_auth_status_led("stopped")
            self.auth_start_btn.setEnabled(True)
            self.auth_stop_btn.setEnabled(False)
        
        # WorldServer status
        if self.world_is_starting:
            self.set_world_status_led("starting")
        elif self.world_process_thread and self.world_process_thread.isRunning():
            self.set_world_status_led("running")
            self.world_start_btn.setEnabled(False)
            self.world_stop_btn.setEnabled(True)
        else:
            self.set_world_status_led("stopped")
            self.world_start_btn.setEnabled(True)
            self.world_stop_btn.setEnabled(False)
        
        # Client status
        if self.client_is_starting:
            self.set_client_status_led("starting")
        elif self.client_process_thread and self.client_process_thread.isRunning():
            self.set_client_status_led("running")
            self.client_start_btn.setEnabled(False)
            self.client_stop_btn.setEnabled(True)
        else:
            self.set_client_status_led("stopped")
            self.client_start_btn.setEnabled(True)
            self.client_stop_btn.setEnabled(False)

        # Webserver status
        if self.web_is_starting:
            self.set_web_status_led("starting")
        elif self.web_process_thread and self.web_process_thread.isRunning():
            self.set_web_status_led("running")
            self.web_start_btn.setEnabled(False)
            self.web_stop_btn.setEnabled(True)
        else:
            self.set_web_status_led("stopped")
            self.web_start_btn.setEnabled(True)
            self.web_stop_btn.setEnabled(False)

    def show_startup_confirmation(self):
        """Show confirmation dialog before killing processes on startup"""
        reply = QMessageBox.question(
            self,
            "ACP Startup",
            "During startup ACP will stop all running processes related to mysqld, authserver, worldserver, wow and apache. Do you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No  # Default to No for safety
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # User confirmed, proceed with cleanup
            self._startup_cleanup_all_processes()
        else:
            # User declined, show message and close app
            QMessageBox.information(
                self,
                "ACP Closing",
                "You selected not to close the running processes. ACP will now close."
            )
            # Close the application completely
            sys.exit(0)

    def on_autorestart_changed(self, state):
        """Handle autorestart checkbox state change"""
        self.autorestart_enabled = state == 2  # 2 = checked, 0 = unchecked
        self.save_config()

    def trigger_autorestart(self):
        """Trigger autorestart by running Start-AutoRestart.bat"""
        if not self.autorestart_enabled or not self.auth_path:
            return
        
        try:
            # Get the authserver directory
            auth_dir = os.path.dirname(self.auth_path)
            restart_script = os.path.join(auth_dir, "Start-AutoRestart.bat")
            
            if os.path.exists(restart_script):
                # Run the script silently in the background
                if sys.platform == "win32":
                    subprocess.Popen(
                        [restart_script],
                        cwd=auth_dir,
                        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
                    )
                else:
                    subprocess.Popen(
                        [restart_script],
                        cwd=auth_dir,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
        except Exception as e:
            # Silently fail - autorestart should not interrupt normal operation
            pass

    def _startup_cleanup_all_processes(self):
        """On app startup, automatically kill any known lingering processes for all rows."""
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            startup_log = os.path.join(LOG_DIR, "startup_cleanup.log")
            with open(startup_log, "a") as lf:
                lf.write("=" * 80 + "\n")
                lf.write(f"--- Startup cleanup at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

            if sys.platform == "win32":
                image_names = [
                    "mysqld.exe",  # MySQL server
                    "mysql.exe",   # MySQL client
                    "authserver.exe",
                    "worldserver.exe",
                    "wow.exe",     # Client
                    "httpd.exe",   # Apache httpd
                    "apache.exe",
                    "ApacheMonitor.exe",
                ]

                # Try graceful termination without force first
                for image in image_names:
                    try:
                        subprocess.run(["taskkill", "/im", image], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    except Exception:
                        pass

                time.sleep(1)

                def is_running(name: str) -> bool:
                    try:
                        result = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {name}"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        return name.lower() in result.stdout.lower()
                    except Exception:
                        return False

                # Force kill any that remain
                for image in image_names:
                    if is_running(image):
                        try:
                            subprocess.run(["taskkill", "/f", "/im", image], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                        except Exception:
                            pass
            else:
                # Unix-like fallback
                try:
                    for pat in ["mysqld", "mysql", "authserver", "worldserver", "wow", "httpd", "apache"]:
                        subprocess.run(["pkill", "-TERM", "-f", pat], capture_output=True)
                    time.sleep(1)
                    for pat in ["mysqld", "mysql", "authserver", "worldserver", "wow", "httpd", "apache"]:
                        subprocess.run(["pkill", "-KILL", "-f", pat], capture_output=True)
                except Exception:
                    pass
        except Exception:
            # Best-effort cleanup; ignore failures
            pass
    
    def open_logs(self):
        """Open log file in default text editor"""
        if os.path.isfile(LOG_FILE):
            try:
                if sys.platform == "win32":
                    os.startfile(LOG_FILE)
                else:
                    subprocess.run(["xdg-open", LOG_FILE])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open log file: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No log file found yet.")

    def open_mysql_config(self):
        """Open MySQL my.ini located one level above the selected mysqld path"""
        if self.mysql_path:
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(self.mysql_path), os.pardir))
            config_file = os.path.join(parent_dir, "my.ini")
            if os.path.isfile(config_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(config_file)
                    else:
                        subprocess.run(["xdg-open", config_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open MySQL config file: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"MySQL config file not found: {config_file}")
        else:
            QMessageBox.information(self, "Info", "No MySQL executable selected.")
    
    def open_auth_logs(self):
        """Open AuthServer log file in default text editor"""
        if self.auth_path:
            auth_log_file = os.path.join(os.path.dirname(self.auth_path), "Logs", "Auth.log")
            if os.path.isfile(auth_log_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(auth_log_file)
                    else:
                        subprocess.run(["xdg-open", auth_log_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open AuthServer log file: {str(e)}")
            else:
                # Log file not found, ask user for correct path
                reply = QMessageBox.question(
                    self, 
                    "Log File Not Found", 
                    f"AuthServer log file not found at:\n{auth_log_file}\n\nWould you like to select the correct log file path?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.select_auth_log_path()
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def select_auth_log_path(self):
        """Open file dialog to select AuthServer log file"""
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select AuthServer Log File", 
            "", 
            "Log files (*.log);;Text files (*.txt);;All files (*.*)"
        )
        if path:
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    subprocess.run(["xdg-open", path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open AuthServer log file: {str(e)}")
    
    def open_auth_config(self):
        """Open AuthServer configuration file in default text editor"""
        if self.auth_path:
            auth_config_file = os.path.join(os.path.dirname(self.auth_path), "configs", "authserver.conf")
            if os.path.isfile(auth_config_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(auth_config_file)
                    else:
                        subprocess.run(["xdg-open", auth_config_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open AuthServer config file: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"AuthServer config file not found: {auth_config_file}")
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def open_world_logs(self):
        """Open WorldServer log file in default text editor"""
        if self.world_path:
            world_log_file = os.path.join(os.path.dirname(self.world_path), "Logs", "Server.log")
            if os.path.isfile(world_log_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(world_log_file)
                    else:
                        subprocess.run(["xdg-open", world_log_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open WorldServer log file: {str(e)}")
            else:
                # Log file not found, ask user for correct path
                reply = QMessageBox.question(
                    self, 
                    "Log File Not Found", 
                    f"WorldServer log file not found at:\n{world_log_file}\n\nWould you like to select the correct log file path?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self.select_world_log_path()
        else:
            QMessageBox.information(self, "Info", "No WorldServer executable selected.")
    
    def select_world_log_path(self):
        """Open file dialog to select WorldServer log file"""
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select WorldServer Log File", 
            "", 
            "Log files (*.log);;Text files (*.txt);;All files (*.*)"
        )
        if path:
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                else:
                    subprocess.run(["xdg-open", path])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open WorldServer log file: {str(e)}")
    
    def open_world_config(self):
        """Open WorldServer configuration file in default text editor"""
        if self.world_path:
            world_config_file = os.path.join(os.path.dirname(self.world_path), "configs", "worldserver.conf")
            if os.path.isfile(world_config_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(world_config_file)
                    else:
                        subprocess.run(["xdg-open", world_config_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open WorldServer config file: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"WorldServer config file not found: {world_config_file}")
        else:
            QMessageBox.information(self, "Info", "No WorldServer executable selected.")

    def open_web_logs(self):
        """Open Webserver parent logs folder (one level up from webserver path, 'logs')"""
        if self.web_path:
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(self.web_path), os.pardir))
            logs_dir = os.path.join(parent_dir, "logs")
            if os.path.isdir(logs_dir):
                try:
                    if sys.platform == "win32":
                        os.startfile(logs_dir)
                    else:
                        subprocess.run(["xdg-open", logs_dir])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open Webserver logs folder: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"Logs folder not found: {logs_dir}")
        else:
            QMessageBox.information(self, "Info", "No Webserver executable selected.")

    def open_web_config(self):
        """Open Webserver httpd.conf (one level up from webserver path, 'conf/httpd.conf')"""
        if self.web_path:
            parent_dir = os.path.abspath(os.path.join(os.path.dirname(self.web_path), os.pardir))
            config_file = os.path.join(parent_dir, "conf", "httpd.conf")
            if os.path.isfile(config_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(config_file)
                    else:
                        subprocess.run(["xdg-open", config_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open Webserver config file: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"Webserver config file not found: {config_file}")
        else:
            QMessageBox.information(self, "Info", "No Webserver executable selected.")

    def open_web_folder(self):
        """Open the directory containing the selected Webserver executable"""
        if self.web_path:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(self.web_path))
                else:
                    subprocess.run(["xdg-open", os.path.dirname(self.web_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open Webserver folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No Webserver executable selected.")

    def open_client_logs(self):
        """Open Client Logs folder (selected_path/Logs)"""
        if self.client_path:
            logs_dir = os.path.join(os.path.dirname(self.client_path), "Logs")
            if os.path.isdir(logs_dir):
                try:
                    if sys.platform == "win32":
                        os.startfile(logs_dir)
                    else:
                        subprocess.run(["xdg-open", logs_dir])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open Client Logs folder: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"Logs folder not found: {logs_dir}")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")

    def open_client_config(self):
        """Open Client config.wtf (selected_path/WTF/config.wtf)"""
        if self.client_path:
            config_file = os.path.join(os.path.dirname(self.client_path), "WTF", "config.wtf")
            if os.path.isfile(config_file):
                try:
                    if sys.platform == "win32":
                        os.startfile(config_file)
                    else:
                        subprocess.run(["xdg-open", config_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open Client config file: {str(e)}")
            else:
                QMessageBox.information(self, "Info", f"Client config file not found: {config_file}")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")

    def open_client_realmlist(self):
        """Open Client realmlist.wtf (selected_path/Data/enUS|enGB/realmlist.wtf)"""
        if self.client_path:
            base_dir = os.path.dirname(self.client_path)
            candidate_paths = [
                os.path.join(base_dir, "Data", "enUS", "realmlist.wtf"),
                os.path.join(base_dir, "Data", "enGB", "realmlist.wtf"),
            ]
            realmlist_file = None
            for path in candidate_paths:
                if os.path.isfile(path):
                    realmlist_file = path
                    break
            if realmlist_file:
                try:
                    if sys.platform == "win32":
                        os.startfile(realmlist_file)
                    else:
                        subprocess.run(["xdg-open", realmlist_file])
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to open Client realmlist: {str(e)}")
            else:
                QMessageBox.information(self, "Info", "realmlist.wtf not found in Data/enUS or Data/enGB.")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")

    def open_client_folder(self):
        """Open the directory containing the selected Client executable"""
        if self.client_path:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(self.client_path))
                else:
                    subprocess.run(["xdg-open", os.path.dirname(self.client_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open Client folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")
    
    def open_mysql_folder(self):
        """Open the directory containing the selected MySQL executable"""
        if self.mysql_path:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(self.mysql_path))
                else:
                    subprocess.run(["xdg-open", os.path.dirname(self.mysql_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open MySQL folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No MySQL executable selected.")

    def open_auth_folder(self):
        """Open the directory containing the selected AuthServer executable"""
        if self.auth_path:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(self.auth_path))
                else:
                    subprocess.run(["xdg-open", os.path.dirname(self.auth_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open AuthServer folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def open_world_folder(self):
        """Open the directory containing the selected WorldServer executable"""
        if self.world_path:
            try:
                if sys.platform == "win32":
                    os.startfile(os.path.dirname(self.world_path))
                else:
                    subprocess.run(["xdg-open", os.path.dirname(self.world_path)])
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open WorldServer folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No WorldServer executable selected.")
    
    def open_lua_scripts_folder(self):
        """Open the lua_scripts folder in the AuthServer directory"""
        if self.auth_path:
            try:
                lua_scripts_path = os.path.join(os.path.dirname(self.auth_path), "lua_scripts")
                if os.path.exists(lua_scripts_path):
                    if sys.platform == "win32":
                        os.startfile(lua_scripts_path)
                    else:
                        subprocess.run(["xdg-open", lua_scripts_path])
                else:
                    QMessageBox.warning(self, "Folder Not Found", f"lua_scripts folder not found at:\n{lua_scripts_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open lua_scripts folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def open_modules_folder(self):
        """Open the configs/modules folder in the AuthServer directory"""
        if self.auth_path:
            try:
                modules_path = os.path.join(os.path.dirname(self.auth_path), "configs", "modules")
                if os.path.exists(modules_path):
                    if sys.platform == "win32":
                        os.startfile(modules_path)
                    else:
                        subprocess.run(["xdg-open", modules_path])
                else:
                    QMessageBox.warning(self, "Folder Not Found", f"modules folder not found at:\n{modules_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open modules folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def open_dbc_folder(self):
        """Open the Data/dbc folder in the AuthServer directory"""
        if self.auth_path:
            try:
                dbc_path = os.path.join(os.path.dirname(self.auth_path), "Data", "dbc")
                if os.path.exists(dbc_path):
                    if sys.platform == "win32":
                        os.startfile(dbc_path)
                    else:
                        subprocess.run(["xdg-open", dbc_path])
                else:
                    QMessageBox.warning(self, "Folder Not Found", f"DBC folder not found at:\n{dbc_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open DBC folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No AuthServer executable selected.")
    
    def open_backup_folder(self):
        """Open the backup folder created by the app"""
        try:
            backup_path = "backup"
            if os.path.exists(backup_path):
                if sys.platform == "win32":
                    os.startfile(backup_path)
                else:
                    subprocess.run(["xdg-open", backup_path])
            else:
                QMessageBox.warning(self, "Folder Not Found", f"Backup folder not found at:\n{os.path.abspath(backup_path)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open backup folder: {str(e)}")
    
    def open_client_data_folder(self):
        """Open the Data folder in the Client directory"""
        if self.client_path:
            try:
                data_path = os.path.join(os.path.dirname(self.client_path), "Data")
                if os.path.exists(data_path):
                    if sys.platform == "win32":
                        os.startfile(data_path)
                    else:
                        subprocess.run(["xdg-open", data_path])
                else:
                    QMessageBox.warning(self, "Folder Not Found", f"Data folder not found at:\n{data_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open Data folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")
    
    def open_addons_folder(self):
        """Open the Interface/Addons folder in the Client directory"""
        if self.client_path:
            try:
                addons_path = os.path.join(os.path.dirname(self.client_path), "Interface", "Addons")
                if os.path.exists(addons_path):
                    if sys.platform == "win32":
                        os.startfile(addons_path)
                    else:
                        subprocess.run(["xdg-open", addons_path])
                else:
                    QMessageBox.warning(self, "Folder Not Found", f"Addons folder not found at:\n{addons_path}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to open Addons folder: {str(e)}")
        else:
            QMessageBox.information(self, "Info", "No Client executable selected.")
    
    def set_auth_status_led(self, status):
        """Set AuthServer LED color based on status: 'stopped', 'starting', 'running'"""
        if status == "running":
            self.auth_status_led.setStyleSheet("QPushButton:disabled { background-color: green; border: 1px solid #c0c0c0; border-radius: 8px; }")
        elif status == "starting":
            self.auth_status_led.setStyleSheet("QPushButton:disabled { background-color: yellow; border: 1px solid #c0c0c0; border-radius: 8px; }")
        else:  # stopped
            self.auth_status_led.setStyleSheet("QPushButton:disabled { background-color: red; border: 1px solid #c0c0c0; border-radius: 8px; }")

    def set_world_status_led(self, status):
        """Set WorldServer LED color based on status: 'stopped', 'starting', 'running'"""
        if status == "running":
            self.world_status_led.setStyleSheet("QPushButton:disabled { background-color: green; border: 1px solid #c0c0c0; border-radius: 8px; }")
        elif status == "starting":
            self.world_status_led.setStyleSheet("QPushButton:disabled { background-color: yellow; border: 1px solid #c0c0c0; border-radius: 8px; }")
        else:  # stopped
            self.world_status_led.setStyleSheet("QPushButton:disabled { background-color: red; border: 1px solid #c0c0c0; border-radius: 8px; }")

    def set_web_status_led(self, status):
        if status == "running":
            self.web_status_led.setStyleSheet("QPushButton:disabled { background-color: green; border: 1px solid #c0c0c0; border-radius: 8px; }")
        elif status == "starting":
            self.web_status_led.setStyleSheet("QPushButton:disabled { background-color: yellow; border: 1px solid #c0c0c0; border-radius: 8px; }")
        else:
            self.web_status_led.setStyleSheet("QPushButton:disabled { background-color: red; border: 1px solid #c0c0c0; border-radius: 8px; }")

    def update_countdown(self):
        """Update countdown labels for all processes"""
        # Update MySQL countdown
        if self.is_starting and self.mysql_countdown_seconds > 0:
            self.mysql_countdown.setText(str(self.mysql_countdown_seconds))
            self.mysql_countdown_seconds -= 1
        elif self.is_starting and self.mysql_countdown_seconds == 0:
            self.mysql_countdown.setText("0")
        elif self.process_thread and self.process_thread.isRunning():
            # Show 0 when running (green LED)
            self.mysql_countdown.setText("0")
        else:
            # Show maximum time when stopped (10 seconds for MySQL)
            self.mysql_countdown.setText("10")
        
        # Update AuthServer countdown
        if self.auth_is_starting and self.auth_countdown_seconds > 0:
            self.auth_countdown.setText(str(self.auth_countdown_seconds))
            self.auth_countdown_seconds -= 1
        elif self.auth_is_starting and self.auth_countdown_seconds == 0:
            self.auth_countdown.setText("0")
        elif self.auth_process_thread and self.auth_process_thread.isRunning():
            # Show 0 when running (green LED)
            self.auth_countdown.setText("0")
        else:
            # Show maximum time when stopped (10 seconds for AuthServer)
            self.auth_countdown.setText("10")
        
        # Update WorldServer countdown
        if self.world_is_starting and self.world_countdown_seconds > 0:
            self.world_countdown.setText(str(self.world_countdown_seconds))
            self.world_countdown_seconds -= 1
        elif self.world_is_starting and self.world_countdown_seconds == 0:
            self.world_countdown.setText("0")
        elif self.world_process_thread and self.world_process_thread.isRunning():
            # Show 0 when running (green LED)
            self.world_countdown.setText("0")
        else:
            # Show maximum time when stopped (120 seconds for WorldServer)
            self.world_countdown.setText("120")

        # Update Client countdown
        if self.client_is_starting and self.client_countdown_seconds > 0:
            self.client_countdown.setText(str(self.client_countdown_seconds))
            self.client_countdown_seconds -= 1
        elif self.client_is_starting and self.client_countdown_seconds == 0:
            self.client_countdown.setText("0")
        elif self.client_process_thread and self.client_process_thread.isRunning():
            # Show 0 when running (green LED)
            self.client_countdown.setText("0")
        else:
            # Show maximum time when stopped (15 seconds for Client)
            self.client_countdown.setText("15")

        # Update Webserver countdown
        if self.web_is_starting and self.web_countdown_seconds > 0:
            self.web_countdown_btn.setText(str(self.web_countdown_seconds))
            self.web_countdown_seconds -= 1
        elif self.web_is_starting and self.web_countdown_seconds == 0:
            self.web_countdown_btn.setText("0")
        elif self.web_process_thread and self.web_process_thread.isRunning():
            self.web_countdown_btn.setText("0")
        else:
            self.web_countdown_btn.setText("10")
    
    # Memory monitoring removed

    # Editor methods
    def open_heidi(self):
        """Open HeidiSQL application"""
        if not self.heidi_path or not os.path.isfile(self.heidi_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open HeidiSQL with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.heidi_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.heidi_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.heidi_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open HeidiSQL: {str(e)}")

    def show_heidi_context_menu(self, position):
        """Show confirmation dialog for HeidiSQL path selection"""
        if self.heidi_path and os.path.isfile(self.heidi_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select HeidiSQL Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.heidi_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "HeidiSQL path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select HeidiSQL Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.heidi_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "HeidiSQL path saved successfully!")

    def open_keira(self):
        """Open Keira application"""
        if not self.keira_path or not os.path.isfile(self.keira_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Keira with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.keira_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.keira_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.keira_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Keira: {str(e)}")

    def show_keira_context_menu(self, position):
        """Show confirmation dialog for Keira path selection"""
        if self.keira_path and os.path.isfile(self.keira_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Keira Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.keira_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "Keira path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Keira Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.keira_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "Keira path saved successfully!")

    def open_mpq_editor(self):
        """Open MPQ Editor application"""
        if not self.mpq_editor_path or not os.path.isfile(self.mpq_editor_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open MPQ Editor with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.mpq_editor_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.mpq_editor_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.mpq_editor_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open MPQ Editor: {str(e)}")

    def show_mpq_context_menu(self, position):
        """Show confirmation dialog for MPQ Editor path selection"""
        if self.mpq_editor_path and os.path.isfile(self.mpq_editor_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select MPQ Editor Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.mpq_editor_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "MPQ Editor path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select MPQ Editor Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.mpq_editor_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "MPQ Editor path saved successfully!")

    def open_wdbx_editor(self):
        """Open WDBX Editor application"""
        if not self.wdbx_editor_path or not os.path.isfile(self.wdbx_editor_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open WDBX Editor with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.wdbx_editor_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.wdbx_editor_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.wdbx_editor_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open WDBX Editor: {str(e)}")

    def show_wdbx_context_menu(self, position):
        """Show confirmation dialog for WDBX Editor path selection"""
        if self.wdbx_editor_path and os.path.isfile(self.wdbx_editor_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select WDBX Editor Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.wdbx_editor_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "WDBX Editor path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select WDBX Editor Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.wdbx_editor_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "WDBX Editor path saved successfully!")

    def open_spell_editor(self):
        """Open Spell Editor application"""
        if not self.spell_editor_path or not os.path.isfile(self.spell_editor_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Spell Editor with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.spell_editor_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.spell_editor_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.spell_editor_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Spell Editor: {str(e)}")

    def show_spell_context_menu(self, position):
        """Show confirmation dialog for Spell Editor path selection"""
        if self.spell_editor_path and os.path.isfile(self.spell_editor_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Spell Editor Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.spell_editor_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "Spell Editor path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Spell Editor Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.spell_editor_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "Spell Editor path saved successfully!")

    def open_notepad_plus(self):
        """Open Notepad++ application"""
        if not self.notepad_plus_path or not os.path.isfile(self.notepad_plus_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Notepad++ with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.notepad_plus_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.notepad_plus_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.notepad_plus_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Notepad++: {str(e)}")

    def show_npp_context_menu(self, position):
        """Show confirmation dialog for Notepad++ path selection"""
        if self.notepad_plus_path and os.path.isfile(self.notepad_plus_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Notepad++ Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.notepad_plus_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "Notepad++ path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Notepad++ Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.notepad_plus_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "Notepad++ path saved successfully!")

    def open_trinity_creator(self):
        """Open Trinity Creator application"""
        if not self.trinity_creator_path or not os.path.isfile(self.trinity_creator_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Trinity Creator with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.trinity_creator_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.trinity_creator_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.trinity_creator_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Trinity Creator: {str(e)}")

    def show_trinity_context_menu(self, position):
        """Show confirmation dialog for Trinity Creator path selection"""
        if self.trinity_creator_path and os.path.isfile(self.trinity_creator_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Trinity Creator Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.trinity_creator_path = path
                    self.save_config()
                    QMessageBox.information(self, "Success", "Trinity Creator path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Trinity Creator Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.trinity_creator_path = path
                self.save_config()
                QMessageBox.information(self, "Success", "Trinity Creator path saved successfully!")

    # Other Editor methods
    def open_other_editor1(self):
        """Open Other Editor 1 application"""
        if not self.other_editor1_path or not os.path.isfile(self.other_editor1_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Other Editor 1 with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.other_editor1_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.other_editor1_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.other_editor1_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Other Editor 1: {str(e)}")

    def show_other_editor1_context_menu(self, position):
        """Show confirmation dialog for Other Editor 1 path selection"""
        if self.other_editor1_path and os.path.isfile(self.other_editor1_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Other Editor 1 Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.other_editor1_path = path
                    # Update button text to show app name without .exe
                    app_name = os.path.splitext(os.path.basename(path))[0]
                    self.other_editor1_text = app_name
                    self.other_editor1_btn.setText(app_name)
                    self.save_config()
                    QMessageBox.information(self, "Success", "Other Editor 1 path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Other Editor 1 Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.other_editor1_path = path
                # Update button text to show app name without .exe
                app_name = os.path.splitext(os.path.basename(path))[0]
                self.other_editor1_text = app_name
                self.other_editor1_btn.setText(app_name)
                self.save_config()
                QMessageBox.information(self, "Success", "Other Editor 1 path saved successfully!")

    def open_other_editor2(self):
        """Open Other Editor 2 application"""
        if not self.other_editor2_path or not os.path.isfile(self.other_editor2_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Other Editor 2 with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.other_editor2_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.other_editor2_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.other_editor2_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Other Editor 2: {str(e)}")

    def show_other_editor2_context_menu(self, position):
        """Show confirmation dialog for Other Editor 2 path selection"""
        if self.other_editor2_path and os.path.isfile(self.other_editor2_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Other Editor 2 Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.other_editor2_path = path
                    # Update button text to show app name without .exe
                    app_name = os.path.splitext(os.path.basename(path))[0]
                    self.other_editor2_text = app_name
                    self.other_editor2_btn.setText(app_name)
                    self.save_config()
                    QMessageBox.information(self, "Success", "Other Editor 2 path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Other Editor 2 Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.other_editor2_path = path
                # Update button text to show app name without .exe
                app_name = os.path.splitext(os.path.basename(path))[0]
                self.other_editor2_text = app_name
                self.other_editor2_btn.setText(app_name)
                self.save_config()
                QMessageBox.information(self, "Success", "Other Editor 2 path saved successfully!")

    def open_other_editor3(self):
        """Open Other Editor 3 application"""
        if not self.other_editor3_path or not os.path.isfile(self.other_editor3_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Other Editor 3 with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.other_editor3_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.other_editor3_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.other_editor3_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Other Editor 3: {str(e)}")

    def show_other_editor3_context_menu(self, position):
        """Show confirmation dialog for Other Editor 3 path selection"""
        if self.other_editor3_path and os.path.isfile(self.other_editor3_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Other Editor 3 Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.other_editor3_path = path
                    # Update button text to show app name without .exe
                    app_name = os.path.splitext(os.path.basename(path))[0]
                    self.other_editor3_text = app_name
                    self.other_editor3_btn.setText(app_name)
                    self.save_config()
                    QMessageBox.information(self, "Success", "Other Editor 3 path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Other Editor 3 Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.other_editor3_path = path
                # Update button text to show app name without .exe
                app_name = os.path.splitext(os.path.basename(path))[0]
                self.other_editor3_text = app_name
                self.other_editor3_btn.setText(app_name)
                self.save_config()
                QMessageBox.information(self, "Success", "Other Editor 3 path saved successfully!")

    def open_other_editor4(self):
        """Open Other Editor 4 application"""
        if not self.other_editor4_path or not os.path.isfile(self.other_editor4_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Other Editor 4 with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.other_editor4_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.other_editor4_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.other_editor4_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Other Editor 4: {str(e)}")

    def show_other_editor4_context_menu(self, position):
        """Show confirmation dialog for Other Editor 4 path selection"""
        if self.other_editor4_path and os.path.isfile(self.other_editor4_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Other Editor 4 Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.other_editor4_path = path
                    # Update button text to show app name without .exe
                    app_name = os.path.splitext(os.path.basename(path))[0]
                    self.other_editor4_text = app_name
                    self.other_editor4_btn.setText(app_name)
                    self.save_config()
                    QMessageBox.information(self, "Success", "Other Editor 4 path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Other Editor 4 Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.other_editor4_path = path
                # Update button text to show app name without .exe
                app_name = os.path.splitext(os.path.basename(path))[0]
                self.other_editor4_text = app_name
                self.other_editor4_btn.setText(app_name)
                self.save_config()
                QMessageBox.information(self, "Success", "Other Editor 4 path saved successfully!")

    def open_other_editor5(self):
        """Open Other Editor 5 application"""
        if not self.other_editor5_path or not os.path.isfile(self.other_editor5_path):
            QMessageBox.warning(self, "Error", "Please right click to select path first!")
            return
        
        # Open Other Editor 5 with proper working directory
        try:
            # Get the directory containing the executable
            working_dir = os.path.dirname(os.path.abspath(self.other_editor5_path))
            
            # Launch GUI application without console window
            if sys.platform == "win32":
                subprocess.Popen(
                    [self.other_editor5_path],
                    cwd=working_dir,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                subprocess.Popen([self.other_editor5_path], cwd=working_dir)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Other Editor 5: {str(e)}")

    def show_other_editor5_context_menu(self, position):
        """Show confirmation dialog for Other Editor 5 path selection"""
        if self.other_editor5_path and os.path.isfile(self.other_editor5_path):
            # Path is set, show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Path Already Set",
                "Do you want to change the actual selected path?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                path, _ = QFileDialog.getOpenFileName(
                    self, 
                    "Select Other Editor 5 Executable", 
                    "", 
                    "Executable files (*.exe);;All files (*.*)"
                )
                if path:
                    self.other_editor5_path = path
                    # Update button text to show app name without .exe
                    app_name = os.path.splitext(os.path.basename(path))[0]
                    self.other_editor5_text = app_name
                    self.other_editor5_btn.setText(app_name)
                    self.save_config()
                    QMessageBox.information(self, "Success", "Other Editor 5 path saved successfully!")
        else:
            # No path set, show file dialog directly
            path, _ = QFileDialog.getOpenFileName(
                self, 
                "Select Other Editor 5 Executable", 
                "", 
                "Executable files (*.exe);;All files (*.*)"
            )
            if path:
                self.other_editor5_path = path
                # Update button text to show app name without .exe
                app_name = os.path.splitext(os.path.basename(path))[0]
                self.other_editor5_text = app_name
                self.other_editor5_btn.setText(app_name)
                self.save_config()
                QMessageBox.information(self, "Success", "Other Editor 5 path saved successfully!")

    def open_account_page(self):
        """Open account management dialog for creating/deleting accounts"""
        # Check if mysqld.exe is running
        try:
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" not in result.stdout:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            else:
                # For Unix-like systems, check for mysqld process
                result = subprocess.run(["pgrep", "mysqld"], capture_output=True)
                if result.returncode != 0:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            
            # Show MySQL connection dialog with database fields
            dialog = MySQLConnectionDialog(self, include_databases=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get connection data from dialog
            connection_data = dialog.get_connection_data()
            mysql_host = connection_data['host']
            mysql_port = connection_data['port']
            mysql_user = connection_data['user']
            mysql_password = connection_data['password']
            auth_db = connection_data['auth_db']
            characters_db = connection_data['characters_db']
            
            # Validate connection data
            if not mysql_host or not mysql_port or not mysql_user or not auth_db or not characters_db:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields (Host, Port, Username, Auth Database, Characters Database).")
                return
            
            # Show account management dialog
            account_dialog = AccountManagementDialog(self, mysql_host, mysql_port, mysql_user, mysql_password, auth_db)
            account_dialog.exec()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open account management: {str(e)}")

    def db_backup_action(self):
        """Database backup action - backup selected databases to SQL files"""
        # Store original button text
        original_text = self.db_backup_btn.text()
        
        # Check if mysqld.exe is running
        try:
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" not in result.stdout:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            else:
                # For Unix-like systems, check for mysqld process
                result = subprocess.run(["pgrep", "mysqld"], capture_output=True)
                if result.returncode != 0:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            
            # Show MySQL connection dialog
            dialog = MySQLConnectionDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get connection data from dialog
            connection_data = dialog.get_connection_data()
            mysql_host = connection_data['host']
            mysql_port = connection_data['port']
            mysql_user = connection_data['user']
            mysql_password = connection_data['password']
            
            # Validate connection data
            if not mysql_host or not mysql_port or not mysql_user:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields (Host, Port, Username).")
                return
            
            # Create backup folder
            backup_dir = "backup"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create timestamp for backup files
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            
            # Get list of databases
            try:
                # Use mysql command to get list of databases
                cmd = [
                    "mysql", 
                    f"--host={mysql_host}", 
                    f"--port={mysql_port}", 
                    f"--user={mysql_user}"
                ]
                if mysql_password:
                    cmd.append(f"--password={mysql_password}")
                cmd.extend(["-e", "SHOW DATABASES;"])
                
                if sys.platform == "win32":
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    QMessageBox.warning(self, "Connection Error", 
                                      f"Failed to connect to MySQL: {result.stderr}")
                    return
                
                # Parse database list (skip header line)
                databases = []
                for line in result.stdout.strip().split('\n')[1:]:
                    db_name = line.strip()
                    if db_name and db_name not in ['information_schema', 'performance_schema', 'mysql', 'sys']:
                        databases.append(db_name)
                
                if not databases:
                    QMessageBox.information(self, "No Databases", "No user databases found to backup.")
                    return
                
                # Show database selection dialog
                selection_dialog = DatabaseSelectionDialog(databases, self)
                if selection_dialog.exec() != QDialog.DialogCode.Accepted:
                    return  # User cancelled
                
                # Get selected databases
                selected_databases = selection_dialog.get_selected_databases()
                if not selected_databases:
                    QMessageBox.information(self, "No Selection", "No databases selected for backup.")
                    return
                
                # Change button state to show backup is running
                self.db_backup_btn.setText("Backing up...")
                self.db_backup_btn.setEnabled(False)
                
                # Create and show progress dialog
                progress_dialog = BackupProgressDialog(len(selected_databases), self)
                progress_dialog.show()
                
                # Backup each database
                success_count = 0
                failed_count = 0
                
                for i, db_name in enumerate(selected_databases):
                    # Check if user cancelled
                    if progress_dialog.cancelled:
                        break
                    
                    # Update progress dialog
                    progress_dialog.update_progress(db_name, i, len(selected_databases))
                    try:
                        backup_file = os.path.join(backup_dir, f"{db_name}_{timestamp}.sql")
                        
                        # Use mysqldump to backup the database
                        dump_cmd = [
                            "mysqldump",
                            f"--host={mysql_host}",
                            f"--port={mysql_port}", 
                            f"--user={mysql_user}",
                            "--single-transaction",
                            "--routines",
                            "--triggers",
                            db_name
                        ]
                        
                        if mysql_password:
                            dump_cmd.append(f"--password={mysql_password}")
                        
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            if sys.platform == "win32":
                                result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, 
                                                     text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)  # 5 minute timeout
                            else:
                                result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, 
                                                     text=True, timeout=300)  # 5 minute timeout
                        
                        if result.returncode == 0:
                            success_count += 1
                        else:
                            failed_count += 1
                            print(f"Failed to backup {db_name}: {result.stderr}")
                            
                    except Exception as e:
                        failed_count += 1
                        print(f"Error backing up {db_name}: {str(e)}")
                
                # Close progress dialog
                progress_dialog.close()
                
                # Restore button state
                self.db_backup_btn.setText(original_text)
                self.db_backup_btn.setEnabled(True)
                
                # Show results
                if progress_dialog.cancelled:
                    QMessageBox.information(self, "Backup Cancelled", "Database backup was cancelled by user.")
                elif success_count > 0:
                    message = f"Backup completed!\n\nSuccessfully backed up {success_count} database(s) to:\n{os.path.abspath(backup_dir)}"
                    if failed_count > 0:
                        message += f"\n\nFailed to backup {failed_count} database(s)."
                    QMessageBox.information(self, "Backup Complete", message)
                else:
                    QMessageBox.warning(self, "Backup Failed", "Failed to backup any databases.")
                    
            except subprocess.TimeoutExpired:
                QMessageBox.warning(self, "Timeout Error", "Database backup operation timed out.")
            except Exception as e:
                QMessageBox.warning(self, "Backup Error", f"An error occurred during backup: {str(e)}")
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to perform database backup: {str(e)}")

    def db_restore_action(self):
        """Database restore action - restore selected backup files to MySQL"""
        # Store original button text
        original_text = self.db_restore_btn.text()
        
        # Check if mysqld.exe is running
        try:
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" not in result.stdout:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            else:
                # For Unix-like systems, check for mysqld process
                result = subprocess.run(["pgrep", "mysqld"], capture_output=True)
                if result.returncode != 0:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            
            # Show MySQL connection dialog
            dialog = MySQLConnectionDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get connection data from dialog
            connection_data = dialog.get_connection_data()
            mysql_host = connection_data['host']
            mysql_port = connection_data['port']
            mysql_user = connection_data['user']
            mysql_password = connection_data['password']
            
            # Validate connection data
            if not mysql_host or not mysql_port or not mysql_user:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields (Host, Port, Username).")
                return
            
            # Check if backup folder exists and has SQL files
            backup_dir = "backup"
            if not os.path.exists(backup_dir):
                QMessageBox.warning(self, "No Backup Folder", "Backup folder not found. Please create backups first.")
                return
            
            # Find all SQL files in backup folder
            backup_files = []
            for file in os.listdir(backup_dir):
                if file.endswith('.sql'):
                    backup_files.append(os.path.join(backup_dir, file))
            
            if not backup_files:
                QMessageBox.warning(self, "No Backup Files", "No SQL backup files found in the backup folder.")
                return
            
            # Show backup file selection dialog
            file_selection_dialog = RestoreFileSelectionDialog(backup_files, self)
            if file_selection_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get selected backup files
            selected_files = file_selection_dialog.get_selected_files()
            if not selected_files:
                QMessageBox.information(self, "No Selection", "No backup files selected for restore.")
                return
            
            # Change button state to show restore is running
            self.db_restore_btn.setText("Restoring...")
            self.db_restore_btn.setEnabled(False)
            
            # Create and show progress dialog
            progress_dialog = RestoreProgressDialog(len(selected_files), self)
            progress_dialog.show()
            
            # Restore each selected file
            success_count = 0
            failed_count = 0
            
            for i, backup_file in enumerate(selected_files):
                # Check if user cancelled
                if progress_dialog.cancelled:
                    break
                
                # Update progress dialog
                progress_dialog.update_progress(backup_file, i, len(selected_files))
                
                try:
                    # Extract database name from filename (remove timestamp and .sql extension)
                    filename = os.path.basename(backup_file)
                    db_name = filename.split('_')[0]  # Get part before first underscore
                    
                    # Use mysql command to restore the database
                    restore_cmd = [
                        "mysql",
                        f"--host={mysql_host}",
                        f"--port={mysql_port}",
                        f"--user={mysql_user}"
                    ]
                    
                    if mysql_password:
                        restore_cmd.append(f"--password={mysql_password}")
                    
                    restore_cmd.append(db_name)
                    
                    # Read the backup file and pipe it to mysql
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        if sys.platform == "win32":
                            result = subprocess.run(restore_cmd, stdin=f, stderr=subprocess.PIPE, 
                                                 text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
                        else:
                            result = subprocess.run(restore_cmd, stdin=f, stderr=subprocess.PIPE, 
                                                 text=True, timeout=300)
                    
                    if result.returncode == 0:
                        success_count += 1
                    else:
                        failed_count += 1
                        print(f"Failed to restore {backup_file}: {result.stderr}")
                        
                except Exception as e:
                    failed_count += 1
                    print(f"Error restoring {backup_file}: {str(e)}")
            
            # Close progress dialog
            progress_dialog.close()
            
            # Restore button state
            self.db_restore_btn.setText(original_text)
            self.db_restore_btn.setEnabled(True)
            
            # Show results
            if progress_dialog.cancelled:
                QMessageBox.information(self, "Restore Cancelled", "Database restore was cancelled by user.")
            elif success_count > 0:
                message = f"Restore completed!\n\nSuccessfully restored {success_count} database(s)."
                if failed_count > 0:
                    message += f"\n\nFailed to restore {failed_count} database(s)."
                QMessageBox.information(self, "Restore Complete", message)
            else:
                QMessageBox.warning(self, "Restore Failed", "Failed to restore any databases.")
                
        except Exception as e:
            # Restore button state in case of error
            self.db_restore_btn.setText(original_text)
            self.db_restore_btn.setEnabled(True)
            QMessageBox.warning(self, "Error", f"Failed to perform database restore: {str(e)}")

    def ch_backup_action(self):
        """Character backup action - backup character data for specific accounts"""
        # Store original button text
        original_text = self.ch_backup_btn.text()
        
        # Check if mysqld.exe is running
        try:
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" not in result.stdout:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            else:
                # For Unix-like systems, check for mysqld process
                result = subprocess.run(["pgrep", "mysqld"], capture_output=True)
                if result.returncode != 0:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            
            # Show MySQL connection dialog with database fields
            dialog = MySQLConnectionDialog(self, include_databases=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get connection data from dialog
            connection_data = dialog.get_connection_data()
            mysql_host = connection_data['host']
            mysql_port = connection_data['port']
            mysql_user = connection_data['user']
            mysql_password = connection_data['password']
            auth_db = connection_data['auth_db']
            characters_db = connection_data['characters_db']
            
            # Validate connection data
            if not mysql_host or not mysql_port or not mysql_user or not auth_db or not characters_db:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields (Host, Port, Username, Auth Database, Characters Database).")
                return
            
            # Get list of accounts from auth database
            try:
                # Use mysql command to get list of accounts
                cmd = [
                    "mysql", 
                    f"--host={mysql_host}", 
                    f"--port={mysql_port}", 
                    f"--user={mysql_user}"
                ]
                if mysql_password:
                    cmd.append(f"--password={mysql_password}")
                cmd.extend(["-e", f"SELECT id, username, email FROM {auth_db}.account ORDER BY username;"])
                
                if sys.platform == "win32":
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode != 0:
                    QMessageBox.warning(self, "Connection Error", 
                                      f"Failed to connect to MySQL or access {auth_db} database: {result.stderr}")
                    return
                
                # Parse account list (skip header line)
                accounts = []
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Check if we have data beyond header
                    for line in lines[1:]:  # Skip header
                        parts = line.strip().split('\t')
                        if len(parts) >= 2:
                            account = {
                                'id': parts[0],
                                'username': parts[1],
                                'email': parts[2] if len(parts) > 2 else 'N/A'
                            }
                            accounts.append(account)
                
                if not accounts:
                    QMessageBox.information(self, "No Accounts", f"No accounts found in the {auth_db} database.")
                    return
                

                
                # Show account selection dialog
                account_selection_dialog = AccountSelectionDialog(accounts, self)
                if account_selection_dialog.exec() != QDialog.DialogCode.Accepted:
                    return  # User cancelled
                
                # Get selected accounts
                selected_accounts = account_selection_dialog.get_selected_accounts()
                if not selected_accounts:
                    QMessageBox.information(self, "No Selection", "No accounts selected for character backup.")
                    return
                
                # Create backup folder
                backup_dir = "backup"
                os.makedirs(backup_dir, exist_ok=True)
                
                # Create timestamp for backup files
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                
                # Change button state to show backup is running
                self.ch_backup_btn.setText("Backing up...")
                self.ch_backup_btn.setEnabled(False)
                
                # Create and show progress dialog
                progress_dialog = BackupProgressDialog(len(selected_accounts), self)
                progress_dialog.show()
                
                # Backup character data for each selected account
                success_count = 0
                failed_count = 0
                
                for i, username in enumerate(selected_accounts):
                    # Check if user cancelled
                    if progress_dialog.cancelled:
                        break
                    
                    # Update progress dialog - set to current account (not completed yet)
                    progress_dialog.status_label.setText(f"Starting backup for account {i + 1} of {len(selected_accounts)}")
                    progress_dialog.current_db_label.setText(f"Current: {username}")
                    progress_dialog.progress_bar.setValue(i)  # Set to current index (0-based)
                    QApplication.processEvents()  # Force UI update
                    
                    try:
                        backup_file = os.path.join(backup_dir, f"characters_{username}_{timestamp}.sql")
                        
                        # Update status to show current operation
                        progress_dialog.status_label.setText(f"Backing up characters for {username}...")
                        QApplication.processEvents()  # Force UI update
                        
                        # Use mysqldump to backup character data for this account
                        # We'll backup the entire characters database without WHERE clause to avoid column issues
                        dump_cmd = [
                            "mysqldump",
                            f"--host={mysql_host}",
                            f"--port={mysql_port}", 
                            f"--user={mysql_user}",
                            "--single-transaction",
                            "--routines",
                            "--triggers",
                            characters_db
                        ]
                        
                        if mysql_password:
                            dump_cmd.append(f"--password={mysql_password}")
                        
                        with open(backup_file, 'w', encoding='utf-8') as f:
                            if sys.platform == "win32":
                                result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, 
                                                     text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
                            else:
                                result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, 
                                                     text=True, timeout=300)
                        
                        if result.returncode == 0:
                            success_count += 1
                            # Update progress to show completion and advance progress bar
                            progress_dialog.status_label.setText(f"Completed backup for {username}")
                            progress_dialog.progress_bar.setValue(i + 1)  # Advance to next position
                            QApplication.processEvents()  # Force UI update
                        else:
                            failed_count += 1
                            # Update progress even for failed backups
                            progress_dialog.status_label.setText(f"Failed backup for {username}")
                            progress_dialog.progress_bar.setValue(i + 1)  # Advance to next position
                            QApplication.processEvents()  # Force UI update
                            
                            error_msg = f"Failed to backup characters for {username}: {result.stderr}"
                            print(error_msg)
                            # Show detailed error in a message box for debugging
                            if failed_count == 1:  # Only show first error to avoid spam
                                QMessageBox.warning(self, "Backup Error", 
                                                  f"Error backing up {username}:\n\n{result.stderr}\n\nThis might be due to:\n- Different database structure\n- Missing permissions\n- Incorrect table names")
                            
                    except Exception as e:
                        failed_count += 1
                        print(f"Error backing up characters for {username}: {str(e)}")
                
                # Close progress dialog
                progress_dialog.close()
                
                # Restore button state
                self.ch_backup_btn.setText(original_text)
                self.ch_backup_btn.setEnabled(True)
                
                # Show results
                if progress_dialog.cancelled:
                    QMessageBox.information(self, "Backup Cancelled", "Character backup was cancelled by user.")
                elif success_count > 0:
                    message = f"Character backup completed!\n\nSuccessfully backed up character data for {success_count} account(s) to:\n{os.path.abspath(backup_dir)}"
                    if failed_count > 0:
                        message += f"\n\nFailed to backup {failed_count} account(s)."
                    QMessageBox.information(self, "Backup Complete", message)
                else:
                    QMessageBox.warning(self, "Backup Failed", "Failed to backup character data for any accounts.")
                    
            except subprocess.TimeoutExpired:
                QMessageBox.warning(self, "Timeout Error", "Character backup operation timed out.")
            except Exception as e:
                QMessageBox.warning(self, "Backup Error", f"An error occurred during character backup: {str(e)}")
                
        except Exception as e:
            # Restore button state in case of error
            self.ch_backup_btn.setText(original_text)
            self.ch_backup_btn.setEnabled(True)
            QMessageBox.warning(self, "Error", f"Failed to perform character backup: {str(e)}")

    def ch_restore_action(self):
        """Character restore action - restore character backup files to MySQL"""
        # Store original button text
        original_text = self.ch_restore_btn.text()
        
        # Check if mysqld.exe is running
        try:
            if sys.platform == "win32":
                result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq mysqld.exe"], 
                                     capture_output=True, text=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                if "mysqld.exe" not in result.stdout:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            else:
                # For Unix-like systems, check for mysqld process
                result = subprocess.run(["pgrep", "mysqld"], capture_output=True)
                if result.returncode != 0:
                    QMessageBox.warning(self, "MySQL Not Running", "MySQL server is not running, please start MySQL first.")
                    return
            
            # Show MySQL connection dialog with database fields
            dialog = MySQLConnectionDialog(self, include_databases=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get connection data from dialog
            connection_data = dialog.get_connection_data()
            mysql_host = connection_data['host']
            mysql_port = connection_data['port']
            mysql_user = connection_data['user']
            mysql_password = connection_data['password']
            auth_db = connection_data['auth_db']
            characters_db = connection_data['characters_db']
            
            # Validate connection data
            if not mysql_host or not mysql_port or not mysql_user or not auth_db or not characters_db:
                QMessageBox.warning(self, "Invalid Input", "Please fill in all required fields (Host, Port, Username, Auth Database, Characters Database).")
                return
            
            # Check if backup folder exists and has character backup files
            backup_dir = "backup"
            if not os.path.exists(backup_dir):
                QMessageBox.warning(self, "No Backup Folder", "Backup folder not found. Please create character backups first.")
                return
            
            # Find all character backup files in backup folder
            character_backup_files = []
            for file in os.listdir(backup_dir):
                if file.startswith("characters_") and file.endswith('.sql'):
                    character_backup_files.append(os.path.join(backup_dir, file))
            
            if not character_backup_files:
                QMessageBox.warning(self, "No Character Backup Files", "No character backup files found in the backup folder.")
                return
            
            # Show character backup file selection dialog
            file_selection_dialog = RestoreFileSelectionDialog(character_backup_files, self)
            if file_selection_dialog.exec() != QDialog.DialogCode.Accepted:
                return  # User cancelled
            
            # Get selected backup files
            selected_files = file_selection_dialog.get_selected_files()
            if not selected_files:
                QMessageBox.information(self, "No Selection", "No character backup files selected for restore.")
                return
            
            # Change button state to show restore is running
            self.ch_restore_btn.setText("Restoring...")
            self.ch_restore_btn.setEnabled(False)
            
            # Create and show progress dialog
            progress_dialog = RestoreProgressDialog(len(selected_files), self)
            progress_dialog.show()
            
            # Restore each selected character backup file
            success_count = 0
            failed_count = 0
            
            for i, backup_file in enumerate(selected_files):
                # Check if user cancelled
                if progress_dialog.cancelled:
                    break
                
                # Update progress dialog - set to current file (not completed yet)
                progress_dialog.status_label.setText(f"Starting restore for file {i + 1} of {len(selected_files)}")
                progress_dialog.current_file_label.setText(f"Current: {os.path.basename(backup_file)}")
                progress_dialog.progress_bar.setValue(i)  # Set to current index (0-based)
                QApplication.processEvents()  # Force UI update
                
                try:
                    # Update status to show current operation
                    progress_dialog.status_label.setText(f"Restoring characters from {os.path.basename(backup_file)}...")
                    QApplication.processEvents()  # Force UI update
                    
                    # Use mysql command to restore the character backup
                    restore_cmd = [
                        "mysql",
                        f"--host={mysql_host}",
                        f"--port={mysql_port}",
                        f"--user={mysql_user}"
                    ]
                    
                    if mysql_password:
                        restore_cmd.append(f"--password={mysql_password}")
                    
                    restore_cmd.append(characters_db)
                    
                    # Read the backup file and pipe it to mysql
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        if sys.platform == "win32":
                            result = subprocess.run(restore_cmd, stdin=f, stderr=subprocess.PIPE, 
                                                 text=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW)
                        else:
                            result = subprocess.run(restore_cmd, stdin=f, stderr=subprocess.PIPE, 
                                                 text=True, timeout=300)
                    
                    if result.returncode == 0:
                        success_count += 1
                        # Update progress to show completion and advance progress bar
                        progress_dialog.status_label.setText(f"Completed restore for {os.path.basename(backup_file)}")
                        progress_dialog.progress_bar.setValue(i + 1)  # Advance to next position
                        QApplication.processEvents()  # Force UI update
                    else:
                        failed_count += 1
                        # Update progress even for failed restores
                        progress_dialog.status_label.setText(f"Failed restore for {os.path.basename(backup_file)}")
                        progress_dialog.progress_bar.setValue(i + 1)  # Advance to next position
                        QApplication.processEvents()  # Force UI update
                        
                        error_msg = f"Failed to restore characters from {backup_file}: {result.stderr}"
                        print(error_msg)
                        # Show detailed error in a message box for debugging
                        if failed_count == 1:  # Only show first error to avoid spam
                            QMessageBox.warning(self, "Restore Error", 
                                              f"Error restoring {os.path.basename(backup_file)}:\n\n{result.stderr}\n\nThis might be due to:\n- Different database structure\n- Missing permissions\n- Corrupted backup file")
                        
                except Exception as e:
                    failed_count += 1
                    # Update progress even for failed restores
                    progress_dialog.status_label.setText(f"Failed restore for {os.path.basename(backup_file)}")
                    progress_dialog.progress_bar.setValue(i + 1)  # Advance to next position
                    QApplication.processEvents()  # Force UI update
                    
                    print(f"Error restoring {backup_file}: {str(e)}")
            
            # Close progress dialog
            progress_dialog.close()
            
            # Restore button state
            self.ch_restore_btn.setText(original_text)
            self.ch_restore_btn.setEnabled(True)
            
            # Show results
            if progress_dialog.cancelled:
                QMessageBox.information(self, "Restore Cancelled", "Character restore was cancelled by user.")
            elif success_count > 0:
                message = f"Character restore completed!\n\nSuccessfully restored {success_count} backup file(s)."
                if failed_count > 0:
                    message += f"\n\nFailed to restore {failed_count} backup file(s)."
                QMessageBox.information(self, "Restore Complete", message)
            else:
                QMessageBox.warning(self, "Restore Failed", "Failed to restore any character backup files.")
                
        except Exception as e:
            # Restore button state in case of error
            self.ch_restore_btn.setText(original_text)
            self.ch_restore_btn.setEnabled(True)
            QMessageBox.warning(self, "Error", f"Failed to perform character restore: {str(e)}")

if __name__ == "__main__":
    # Suppress PyInstaller temporary directory cleanup warnings
    import warnings
    warnings.filterwarnings("ignore", message="Failed to remove temporary directory")
    
    # Also suppress specific temp directory warnings
    import logging
    logging.getLogger().setLevel(logging.ERROR)
    
    app = QApplication(sys.argv)
    
    # Optimize application settings for better performance
    app.setAttribute(Qt.AA_EnableHighDpiScaling, False)  # Disable high DPI scaling for better performance
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, False)     # Disable high DPI pixmaps
    
    # Speed up tooltip display
    app.setStyleSheet("""
        QToolTip {
            background-color: #fff8dc;
            color: #856404;
            border: 1px solid #ffeaa7;
            border-radius: 4px;
            padding: 4px;
        }
    """)
    
    # Set faster tooltip delay (default is usually 1000ms, set to 200ms)
    app.setProperty("toolTipDelay", 200)
    
    window = MySQLLauncher()
    window.show()
    sys.exit(app.exec())
