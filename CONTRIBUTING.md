# Contributing to AzerothCore Control Panel (ACP)

Thank you for your interest in contributing to ACP! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Types of Contributions

We welcome various types of contributions:

- **Bug Reports**: Report issues you encounter
- **Feature Requests**: Suggest new features or improvements
- **Code Contributions**: Submit pull requests with code changes
- **Documentation**: Improve or add documentation
- **Testing**: Help test the application and report issues
- **Translation**: Help translate the interface to other languages

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Basic knowledge of Python and Qt/PySide6

### Development Setup

1. **Fork the Repository**
   ```bash
   git clone https://github.com/yourusername/ACP.git
   cd ACP
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create a Virtual Environment** (Recommended)
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Run the Application**
   ```bash
   python ACP.py
   ```

## 📝 Development Guidelines

### Code Style

- Follow PEP 8 Python style guidelines
- Use meaningful variable and function names
- Add docstrings to classes and functions
- Keep functions focused and concise
- Use type hints where appropriate

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add new database backup feature
fix: resolve MySQL connection timeout issue
docs: update installation instructions
style: improve button layout and spacing
refactor: reorganize configuration management
```

### Pull Request Process

1. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Your Changes**
   - Write clean, well-documented code
   - Add tests if applicable
   - Update documentation as needed

3. **Test Your Changes**
   - Run the application to ensure it works
   - Test on different platforms if possible
   - Check for any new issues

4. **Submit a Pull Request**
   - Provide a clear description of changes
   - Reference any related issues
   - Include screenshots for UI changes

### Code Review

All contributions require review before merging:

- Address review comments promptly
- Make requested changes or explain why they're not needed
- Ensure all tests pass
- Update documentation if needed

## 🐛 Reporting Issues

### Bug Report Template

When reporting bugs, please include:

- **Description**: Clear description of the problem
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**: OS, Python version, dependencies
- **Screenshots**: If applicable
- **Logs**: Any error messages or logs

### Example Bug Report

```markdown
## Bug Description
The MySQL server fails to start when clicking the start button.

## Steps to Reproduce
1. Launch ACP
2. Click the MySQL start button
3. Observe error message

## Expected Behavior
MySQL server should start successfully.

## Actual Behavior
Error dialog appears: "Failed to start MySQL server"

## Environment
- OS: Windows 10
- Python: 3.9.7
- PySide6: 6.5.0

## Additional Information
Error occurs only when running as non-administrator.
```

## ✨ Feature Requests

### Feature Request Template

```markdown
## Feature Description
Brief description of the requested feature.

## Use Case
Explain why this feature would be useful.

## Proposed Implementation
Optional: Suggest how to implement the feature.

## Alternatives
Any alternatives you've considered.

## Additional Context
Any other relevant information.
```

## 🧪 Testing

### Testing Guidelines

- Test your changes thoroughly
- Test on different operating systems if possible
- Test edge cases and error conditions
- Ensure the application remains stable

### Running Tests

```bash
# Basic functionality test
python ACP.py

# Check for syntax errors
python -m py_compile ACP.py

# Run with different Python versions (if available)
python3.8 ACP.py
python3.9 ACP.py
python3.10 ACP.py
```

## 📚 Documentation

### Documentation Standards

- Keep documentation up to date with code changes
- Use clear, concise language
- Include examples where helpful
- Update README.md for significant changes
- Add inline comments for complex code

## 🔒 Security

### Security Guidelines

- Never commit sensitive information (passwords, API keys)
- Report security vulnerabilities privately
- Follow secure coding practices
- Validate all user inputs
- Use secure defaults

## 📞 Getting Help

### Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For general questions and discussions
- **Pull Requests**: For code contributions

### Questions?

If you have questions about contributing:

1. Check existing issues and discussions
2. Search the documentation
3. Open a new discussion
4. Be patient and respectful

## 🙏 Recognition

Contributors will be recognized in:

- Project README
- Release notes
- Contributor statistics
- Special acknowledgments for significant contributions

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project (MIT License).

---

Thank you for contributing to ACP! Your help makes this project better for everyone.
