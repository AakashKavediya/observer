# Microsoft Store Readiness & Submission Checklist

This document details the complete requirements and validation steps for submitting Observer to the Microsoft Store on Windows 10/11 x64.

---

## 1. Store Metadata & Policy Compliance

### 1.1 Privacy Policy URL & Offline Declarations
- **Privacy Policy Statement**: *"Observer operates 100% offline on your device. It collects no personal data, transmits no analytics, records no video or audio, and makes no network connections."*
- **Privacy Policy URL Placeholder**: `https://observer-app.org/privacy` (host the content of `PRIVACY.md`).
- **Store Declarations**: Under Microsoft Partner Center -> App properties -> Data disclosure: Declare that the app **does not** collect, store, or share any personal information.

### 1.2 Webcam Device Capability
- In the app manifest / Windows declarations, the camera capability `webcam` is declared for facial landmark feature extraction.
- **Handling Permission Denial**: If the user has disabled Camera access in Windows Settings (*Privacy & Security -> Camera*), Observer captures this state and displays a friendly inline message: *"Camera access is turned off in Windows Settings. Click here to open settings or continue in demo mode."*

### 1.3 Age Rating (IARC)
- **Target Category**: Productivity / Accessibility / Health & Wellbeing companion.
- **IARC Questionnaire**: No violence, no profanity, no user-to-user communications, no location sharing, no in-app purchases. Standard rating: **All Ages / Everyone (PEGI 3, ESRB Everyone)**.

### 1.4 Accessibility Statement (WCAG 2.2 AA)
- High contrast support matching system accessibility colors.
- Full keyboard navigation (all interactive elements focusable with visible focus rings).
- Screen-reader accessible ARIA roles (`role="main"`, `role="banner"`, `role="status"`).
- `prefers-reduced-motion` honored across all UI transitions.
- Fully scalable typography using Atkinson Hyperlegible (SIL OFL) humanist typeface.

---

## 2. Packaging & Code-Signing

### 2.1 Packaging Target: MSIX vs Signed InnoSetup
- **Recommended**: MSIX package via Tauri CLI (`tauri build --bundles msix` or `appx`).
- MSIX provides seamless installation, sandboxed application identity, clean uninstalls without residual files, and native auto-updates through the Microsoft Store infrastructure.

### 2.2 Code-Signing Certificate
- For sideloading or direct installer testing: Sign binaries with an Authenticode code-signing certificate (Standard or EV):
  ```powershell
  signtool sign /fd SHA256 /a /tr http://timestamp.digicert.com /td SHA256 "src-tauri\target\release\Observer.exe"
  ```
- When submitted via Partner Center for Microsoft Store ingestion, Microsoft signs the MSIX package with its Store root certificate.

---

## 3. PyInstaller Antivirus False-Positive Mitigation

PyInstaller one-dir bundles can occasionally trigger heuristic false positives in generic antivirus engines. The following practices are enforced:
1. **onedir Packaging**: Shipped as a folder containing the executable and shared libraries (`observer_engine.exe` + `.dll` files) rather than a self-extracting `onefile` binary.
2. **Deterministic Metadata**: Include complete Windows version resource information (File Description, Company Name, Legal Copyright, Product Name) in `observer_engine.spec`.
3. **Authenticode Signing**: Sign both `observer_engine.exe` and `Observer.exe` before bundling.
4. **Offline Clean Environment**: Build on clean runner with verified dependency hashes.

---

## 4. Clean-Machine Install Verification

Run `scripts/verify_clean_machine.ps1` on a pristine Windows 10/11 VM without Node.js, Python, or Rust installed:
1. Run installer. Verify:
   * No UAC elevation prompt (per-user install into `%LOCALAPPDATA%\Programs\Observer`).
   * App launches and loads Atkinson Hyperlegible font offline.
   * Welcome screen appears with consent gating.
   * Model file `face_landmarker.task` is loaded from the internal bundled directory.
   * System tray icon appears with status and Pause options.
