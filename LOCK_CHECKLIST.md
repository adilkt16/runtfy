# Manual Verification Checklist: Lock-When-Away

This checklist covers manual verification of the `--lock-when-away` feature on macOS and Linux (FR7, FR8, FR12).

---

## Part 1: macOS Verification

Tested on macOS Monterey, Ventura, Sonoma, and Sequoia.

### Prerequisites

1. Confirm macOS Lock Screen settings:
   - Open **System Settings** → **Lock Screen** (or **Security & Privacy** on older macOS).
   - Ensure **Require password after display turns off or screen saver begins** is set to **Immediately**.
2. Install `runtfy` locally:
   ```bash
   pip install -e .
   ```
3. Initialize a test topic and subscribe on your phone:
   ```bash
   runtfy init
   ```
   Confirm you have subscribed to the topic in the ntfy app.

### Test Cases (macOS)

#### 1. Basic Screen Lock
- [ ] Run:
  ```bash
  runtfy --lock-when-away sleep 10
  ```
- [ ] **Expected**:
  - The display turns off / locks immediately via `pmset displaysleepnow`.
  - No permission prompts (Accessibility or Input Monitoring) appear.
  - After 10 seconds, wake the screen and log in.
  - Phone receives notification: `runtfy: sleep finished` (`Status: ✓ success`).

#### 2. Input Alert During Lock
- [ ] Run:
  ```bash
  runtfy --lock-when-away sleep 30
  ```
- [ ] Wait 3 seconds for the screen to lock and settle.
- [ ] Move the mouse or press any key on the keyboard while the screen is locked.
- [ ] **Expected**:
  - Phone receives notification:
    - **Title**: `runtfy: input detected`
    - **Body**: `Someone typed or moved the mouse while your screen was locked.`

#### 3. Cooldown Verification (60-second cooldown)
- [ ] Keep the screen locked after triggering Test Case 2.
- [ ] Within 10–20 seconds of the first input alert, move the mouse again.
- [ ] **Expected**:
  - **No second notification** is sent immediately (enforcing the 60-second cooldown).
- [ ] Wait at least 65 seconds, then move the mouse again.
- [ ] **Expected**:
  - Phone receives a second notification: `runtfy: input detected`.

#### 4. Lock Failure Fallback (FR12)
- [ ] Simulate a lock failure (e.g. running in an environment where `pmset` fails):
  ```bash
  runtfy --lock-when-away echo "lock failure test"
  ```
- [ ] **Expected**:
  - If locking cannot be performed, the command (`echo "lock failure test"`) still executes and exits with its normal exit code.
  - A notification alert is sent indicating that the screen could not be locked.

---

## Part 2: Linux Verification (v0.1)

Tested on Ubuntu 22.04+ (GNOME / systemd-logind).

### Linux Scope & Behavior
- On Linux, `--lock-when-away` locks the session using `loginctl lock-session` (with fallbacks `xdg-screensaver lock` and `gnome-screensaver-command --lock`).
- **Input watching is NOT implemented on Linux in v0.1** (PRD non-goal). Linux receives the screen lock only.
- If locking fails, the command still runs and the user is alerted (FR12).

### Test Cases (Linux)

#### 1. Basic Screen Lock (loginctl / xdg-screensaver)
- [ ] In a graphical Linux session (X11 or Wayland), run:
  ```bash
  runtfy --lock-when-away sleep 10
  ```
- [ ] **Expected**:
  - The desktop locks immediately via `loginctl lock-session` (or fallback).
  - The command runs uninterrupted in the background.
  - After 10 seconds, unlock the screen.
  - Phone receives notification: `runtfy: sleep finished` (`Status: ✓ success`).

#### 2. No Input Alerts on Linux (v0.1 Scope)
- [ ] Run:
  ```bash
  runtfy --lock-when-away sleep 20
  ```
- [ ] Move the mouse and type while locked.
- [ ] **Expected**:
  - No input alert is sent (confirming input watching is inactive on Linux in v0.1).

#### 3. Lock Failure Fallback (FR12)
- [ ] Run on a headless terminal or SSH session without a graphical session manager:
  ```bash
  runtfy --lock-when-away echo "headless test"
  ```
- [ ] **Expected**:
  - A warning message is output indicating lock failure.
  - The command runs and outputs `"headless test"`, exiting with code 0.
  - Phone receives an alert that the screen could not be locked.
