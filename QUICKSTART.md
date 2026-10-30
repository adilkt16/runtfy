# 🔔 runtfy — Quick Start Guide

> A lightweight, zero-dependency CLI tool that pings your phone whenever long-running terminal commands finish or when Claude Code asks for user input.

---

## ⚡ 2-Minute Setup

### 1. Install the phone app
Download the free **ntfy** app (no account/login required):
- **iOS**: [Apple App Store](https://apps.apple.com/app/ntfy/id1625396347)
- **Android**: [Google Play](https://play.google.com/store/apps/details?id=io.heckel.ntfy) or [F-Droid](https://f-droid.org/packages/io.heckel.ntfy/)

### 2. Install runtfy
```bash
pip install runtfy
```

### 3. Pair your phone
Run:
```bash
runtfy init
```
Open the **ntfy** app on your phone, tap **`+`** (Subscribe to topic), and enter the topic name displayed in your terminal.

---

## 🧪 How to Test

### 1. Test a simple command
```bash
runtfy sleep 3
```
Your phone will buzz: *"runtfy: sleep finished ✓ success"*.

### 2. Wrap your regular workflow
Prefix any long command with `runtfy`:
```bash
runtfy npm run build
runtfy pytest
runtfy cargo build --release
runtfy docker build -t myapp .
```
You can walk away from your desk — your phone will notify you the moment it completes.

### 3. Test failure alerts
```bash
runtfy sh -c 'echo "build failed"; exit 1'
```
You will get an alert indicating the non-zero exit code.

### 4. Lock screen when stepping away *(Optional)*
```bash
runtfy --lock-when-away make test
```
Automatically locks your macOS or Linux display if you step away from your machine.

### 5. Claude Code notifications *(Optional)*
```bash
runtfy install-hooks
```
Sends a ping whenever Claude Code needs input or finishes a task.

---

## 🔗 Links
- **GitHub**: https://github.com/adilkt16/runtfy
- **PyPI**: https://pypi.org/project/runtfy/
