# Security Policy

## Supported Versions

We actively maintain and provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you believe you have found a security vulnerability, please report it to us as described below.

### **Please do NOT report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

### How to Report

1. **Email Security Team**: Send an email to [security@yourdomain.com](mailto:security@yourdomain.com)
   - Use the subject line: `[SECURITY] ACP Vulnerability Report`
   - Include a detailed description of the vulnerability
   - Provide steps to reproduce the issue
   - Include any relevant code or configuration examples

2. **Private Security Advisory**: If you prefer, you can create a private security advisory on GitHub:
   - Go to the Security tab in the repository
   - Click "Report a vulnerability"
   - Fill out the security advisory form

### What to Include

When reporting a vulnerability, please provide:

- **Description**: Clear description of the security issue
- **Impact**: Potential impact of the vulnerability
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Proof of Concept**: Code or configuration that demonstrates the vulnerability
- **Environment**: OS, Python version, and any relevant configuration
- **Timeline**: If you plan to disclose the vulnerability publicly

### Response Timeline

- **Initial Response**: Within 48 hours of receiving the report
- **Assessment**: Security team will assess the report within 1 week
- **Updates**: Regular updates on the status and timeline for fixes
- **Resolution**: Fixes will be prioritized based on severity

### Severity Levels

We use the following severity levels to classify vulnerabilities:

- **Critical**: Immediate action required, potential for complete system compromise
- **High**: Significant security impact, requires prompt attention
- **Medium**: Moderate security impact, should be addressed soon
- **Low**: Minor security impact, can be addressed in regular updates

## Security Best Practices

### For Users

- Keep the application updated to the latest version
- Use strong, unique passwords for database connections
- Run the application with minimal required permissions
- Regularly review and audit access logs
- Use firewalls to restrict network access
- Keep your operating system and Python environment updated

### For Developers

- Follow secure coding practices
- Validate all user inputs
- Use parameterized queries for database operations
- Implement proper authentication and authorization
- Use HTTPS for any network communications
- Regularly update dependencies
- Conduct security code reviews

## Security Features

### Built-in Security Measures

- **Input Validation**: All user inputs are validated and sanitized
- **SQL Injection Protection**: Parameterized queries prevent SQL injection
- **File Path Validation**: Secure file operations prevent path traversal attacks
- **Process Isolation**: Server processes run with appropriate permissions
- **Configuration Security**: Sensitive configuration is stored securely

### Security Configuration

- **Database Security**: Secure MySQL connection handling
- **File Permissions**: Appropriate file and directory permissions
- **Logging**: Security-relevant events are logged
- **Error Handling**: Secure error messages that don't leak sensitive information

## Disclosure Policy

### Coordinated Disclosure

We follow a coordinated disclosure policy:

1. **Private Reporting**: Vulnerabilities are reported privately
2. **Assessment**: Security team assesses the vulnerability
3. **Fix Development**: Fixes are developed and tested
4. **Release**: Fixed version is released with security notes
5. **Public Disclosure**: Vulnerability details are disclosed after fixes are available

### Public Disclosure Timeline

- **Critical/High**: Disclosed within 30 days of fix availability
- **Medium**: Disclosed within 60 days of fix availability
- **Low**: Disclosed within 90 days of fix availability

## Security Updates

### Update Notifications

- Security updates are announced in release notes
- Critical security fixes may be released as hotfixes
- Users are encouraged to update promptly
- Security advisories are published for significant issues

### Update Process

1. **Security Fix**: Vulnerability is fixed in development
2. **Testing**: Fix is thoroughly tested
3. **Release**: Fixed version is released
4. **Notification**: Users are notified of the security update
5. **Documentation**: Security advisory is published

## Contact Information

### Security Team

- **Email**: [security@yourdomain.com](mailto:security@yourdomain.com)
- **Response Time**: Within 48 hours
- **Escalation**: For urgent issues, include `[URGENT]` in subject line

### General Security Questions

For general security questions or best practices:

- **GitHub Discussions**: Use the Security category
- **Documentation**: Check the security section in our docs
- **Community**: Ask in our community channels

## Acknowledgments

We thank security researchers and community members who responsibly report vulnerabilities. Your contributions help make ACP more secure for everyone.

---

**Remember**: Security is everyone's responsibility. If you see something, say something!
