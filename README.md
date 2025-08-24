# Azerothcore Control Panel (ACP)

A comprehensive desktop application for managing AzerothCore private server components with an intuitive graphical interface.

## 🚀 Features

- **Server Management**: Start/stop/restart AzerothCore server components (Auth, World, Client, Web)
- **MySQL Integration**: Direct MySQL server management with connection settings
- **Database Operations**: Backup and restore databases with progress tracking
- **Process Monitoring**: Real-time status monitoring of all server processes
- **Auto-restart**: Configurable auto-restart functionality for crashed services
- **Editor Integration**: Quick access to popular development tools and editors
- **Work Folders**: Organized access to server directories and files
- **Modern UI**: Beautiful gradient-based interface with responsive design

## 📸 Screenshot

![ACP Main Window](https://github.com/raulfabi/ACP/raw/main/screenshots/acp-main-window.png)

*The ACP main interface showing server controls, database management, and process monitoring features.*

## 🎥 Video Demo

Watch ACP in action! [View Demo Video](https://github.com/raulfabi/ACP/raw/main/videos/acp-demo.mp4)

*Comprehensive demonstration of ACP features including server management, database operations, and process monitoring.*

## 🛠️ Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows (primary), Linux/macOS (experimental)
- **Dependencies**: PySide6, win32api (Windows)

## 📦 Installation

### Prerequisites

1. Install Python 3.8+ from [python.org](https://python.org)
2. Install required dependencies:

```bash
pip install PySide6
```

For Windows users:
```bash
pip install pywin32
```

### Setup

1. Clone the repository:
```bash
git clone https://github.com/raulfabi/ACP.git
cd ACP
```

2. Run the application:
```bash
python ACP.py
```

## 🔧 Configuration

The application automatically creates configuration files in the `config/` directory:

- **config.json**: Application settings and paths
- **logs/**: Application and process logs

### First Run Setup

1. Launch the application
2. Configure MySQL connection settings
3. Set paths to your AzerothCore server directories
4. Configure editor paths for development tools

## 📁 Project Structure

```
ACP/
├── ACP.py              # Main application file
├── app_icon.ico        # Application icon
├── background*.png      # UI background images
├── icons/              # Application icons
├── screenshots/         # Application screenshots
├── videos/              # Demo videos and tutorials
├── config/             # Configuration files (auto-created)
└── logs/               # Log files (auto-created)
```

## 🎯 Usage

### Starting Services

1. **MySQL Server**: Click the MySQL button to start/stop the database server
2. **Auth Server**: Launch the authentication server
3. **World Server**: Start the game world server
4. **Client**: Launch the game client
5. **Web Server**: Start the web interface

### Database Management

- **Backup**: Select databases and create backups with progress tracking
- **Restore**: Restore databases from backup files
- **Connection**: Configure MySQL connection settings

### Process Monitoring

- Real-time status indicators for all services
- Countdown timers for startup processes
- Auto-restart functionality for crashed services

## 🚨 Troubleshooting

### Common Issues

1. **MySQL Connection Failed**
   - Verify MySQL server is running
   - Check connection credentials
   - Ensure proper permissions

2. **Service Won't Start**
   - Verify executable paths are correct
   - Check if ports are already in use
   - Review log files in the `logs/` directory

3. **Permission Errors**
   - Run as administrator (Windows)
   - Check file/folder permissions
   - Verify antivirus exclusions

### Logs

Check the `logs/` directory for detailed error information:
- `mysql_process.log`: MySQL server logs
- Application logs for debugging

## 🤝 Contributing

We welcome contributions! Please feel free to submit issues, feature requests, or pull requests.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **AzerothCore**: The amazing open-source WoW server emulator
- **PySide6**: Modern Python bindings for Qt
- **Community**: All contributors and users

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/raulfabi/ACP/issues)
- **Discussions**: [GitHub Discussions](https://github.com/raulfabi/ACP/discussions)
- **Wiki**: [Project Wiki](https://github.com/raulfabi/ACP/wiki)

---

**Note**: This application is designed for managing AzerothCore private servers. Please ensure you comply with all applicable terms of service and licensing requirements.
