# Installation Guide

This guide will walk you through installing and setting up AzerothCore Control Panel (ACP) on your system.

## Prerequisites

Before installing ACP, ensure you have the following:

### System Requirements

- **Operating System**: Windows 10/11 (primary), Linux, macOS (experimental)
- **Python**: 3.8 or higher
- **Memory**: Minimum 4GB RAM, recommended 8GB+
- **Storage**: At least 500MB free space
- **Permissions**: Administrator access (Windows) or sudo access (Linux/macOS)

### Required Software

- **Python 3.8+**: Download from [python.org](https://python.org)
- **Git**: For cloning the repository
- **MySQL Server**: For database operations (optional but recommended)

## Installation Methods

### Method 1: Clone from GitHub (Recommended)

1. **Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/ACP.git
   cd ACP
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**
   ```bash
   python ACP.py
   ```

### Method 2: Download Release

1. **Download Latest Release**
   - Go to [Releases](https://github.com/yourusername/ACP/releases)
   - Download the latest release for your platform
   - Extract the archive to your desired location

2. **Install Dependencies**
   ```bash
   cd ACP
   pip install -r requirements.txt
   ```

3. **Run the Application**
   ```bash
   python ACP.py
   ```

### Method 3: Using pip (Future)

```bash
pip install azerothcore-control-panel
acp
```

## Platform-Specific Instructions

### Windows

#### Prerequisites
- Install Python 3.8+ from [python.org](https://python.org)
- Ensure "Add Python to PATH" is checked during installation
- Install Git from [git-scm.com](https://git-scm.com)

#### Installation Steps
1. Open Command Prompt or PowerShell as Administrator
2. Clone the repository:
   ```cmd
   git clone https://github.com/yourusername/ACP.git
   cd ACP
   ```
3. Install dependencies:
   ```cmd
   pip install -r requirements.txt
   ```
4. Run the application:
   ```cmd
   python ACP.py
   ```

#### Troubleshooting
- **Python not found**: Ensure Python is added to PATH
- **Permission errors**: Run Command Prompt as Administrator
- **pip not found**: Reinstall Python with PATH option

### Linux

#### Prerequisites
- Python 3.8+ (usually pre-installed)
- Git
- pip3

#### Installation Steps
1. Open terminal
2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ACP.git
   cd ACP
   ```
3. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python3 ACP.py
   ```

#### Troubleshooting
- **Module not found**: Use `pip3` instead of `pip`
- **Permission denied**: Use `sudo` for system-wide installation
- **Display issues**: Ensure X11 forwarding is enabled for remote connections

### macOS

#### Prerequisites
- Python 3.8+ (install via Homebrew or python.org)
- Git
- pip3

#### Installation Steps
1. Open Terminal
2. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ACP.git
   cd ACP
   ```
3. Install dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python3 ACP.py
   ```

#### Troubleshooting
- **Python version**: Use `python3` command
- **Permission issues**: Check Gatekeeper settings
- **Dependency conflicts**: Use virtual environment

## Virtual Environment (Recommended)

Using a virtual environment prevents dependency conflicts:

### Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

### Install in Virtual Environment

```bash
pip install -r requirements.txt
python ACP.py
```

### Deactivate Virtual Environment

```bash
deactivate
```

## Dependencies

### Core Dependencies

- **PySide6**: Qt6 bindings for Python
- **pywin32**: Windows API access (Windows only)

### Optional Dependencies

- **pytest**: For running tests
- **black**: Code formatting
- **flake8**: Code linting

### Installing Dependencies

```bash
# Install core dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If available

# Install specific dependency
pip install PySide6
```

## Configuration

### First Run Setup

1. **Launch ACP**
   ```bash
   python ACP.py
   ```

2. **Configure MySQL Connection**
   - Enter database host, port, username, and password
   - Test connection to ensure settings are correct

3. **Set Server Paths**
   - Configure paths to AzerothCore server directories
   - Set editor paths for development tools

4. **Save Configuration**
   - Configuration is automatically saved to `config/config.json`

### Configuration Files

- **config/config.json**: Main application configuration
- **logs/**: Application and process logs
- **backups/**: Database backup files (if created)

## Verification

### Test Installation

1. **Run Basic Test**
   ```bash
   python -c "import ACP; print('Installation successful!')"
   ```

2. **Check Dependencies**
   ```bash
   python -c "import PySide6; print('PySide6 installed successfully')"
   ```

3. **Launch Application**
   ```bash
   python ACP.py
   ```

### Common Issues

- **Import errors**: Check Python version and dependencies
- **Display issues**: Verify Qt installation
- **Permission errors**: Check user permissions
- **Path issues**: Ensure correct working directory

## Updating

### Update from GitHub

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### Update Dependencies

```bash
pip install --upgrade PySide6
pip install --upgrade pywin32  # Windows only
```

## Uninstallation

### Remove Application

```bash
# Remove source code
rm -rf ACP/

# Remove configuration (optional)
rm -rf ~/.config/ACP/  # Linux/macOS
rm -rf %APPDATA%\ACP\  # Windows
```

### Remove Dependencies

```bash
pip uninstall PySide6 pywin32
```

## Support

### Getting Help

- **Documentation**: Check this guide and other docs
- **Issues**: Report problems on GitHub
- **Discussions**: Ask questions in GitHub Discussions
- **Wiki**: Check project wiki for additional information

### Troubleshooting

- **Logs**: Check `logs/` directory for error information
- **Configuration**: Verify `config/config.json` settings
- **Dependencies**: Ensure all required packages are installed
- **Permissions**: Check file and directory permissions

---

**Next Steps**: After installation, see the [User Guide](USER_GUIDE.md) for using ACP.
