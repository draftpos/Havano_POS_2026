# Havano POS Licensing Implementation Plan

## 1. Overview
The goal is to implement a robust, highly secure software licensing system for Havano POS. The system will lock the software to a specific physical computer using hardware fingerprinting, utilize cryptographic signatures to prevent key forgery, and implement database-level checks to prevent time-tampering (clock rollback attacks).

## 2. Core Security Concepts
* **Hardware Fingerprinting (Machine ID):** We will combine the computer's MAC address and Motherboard Serial Number into a single, clean 16-character string. This ensures the license cannot be copied to another machine.
* **Cryptographic Signatures:** The license string is secured using **Fernet Symmetric Encryption** (from Python's `cryptography` library). It encrypts the payload using a 32-byte key derived from the Machine ID and a Secret Key, ensuring that a stolen license blob cannot be decrypted or used on any other hardware.
* **Anti-Time Travel Checks:** The system will check the most recent transaction date in the SQL Server database. If the computer's clock is older than the last recorded transaction, the system will instantly detect the rollback and lock the POS.

## 3. Files and Components to Build

### A. The Vendor Tool (For Your Eyes Only)
* **`keygen.py`**: A small, standalone Python script that you will run on your personal computer. You will input the client's `Machine ID` and the number of days the license is valid for. It will output the encrypted `License Key` that you send to the client.

### B. The POS Application Components
* **`utils/hardware.py`**: A utility script responsible for running the Windows commands (`uuid` and `wmic`) to generate and return the clean 16-character `Machine ID`.
* **`utils/license_manager.py`**: The core verification engine. It will:
  1. Read the saved license key from a local file or the database.
  2. Verify the cryptographic signature.
  3. Compare the Machine ID in the key against the actual physical hardware.
  4. Compare the Expiration Date against the computer's clock AND the latest SQL database transaction date.
* **`views/dialogs/license_dialog.py`**: A sleek PyQt6 popup window. If the `license_manager.py` detects an invalid, missing, or expired license, this dialog will appear. It will display the user's `Machine ID` (so they can send it to you) and provide a text box for them to paste their new `License Key`.

### C. Integration
* **`main.py`**: We will inject the `license_manager` check right before the login screen appears. If the license is invalid, it will launch the `license_dialog`. If they exit the dialog without providing a valid key, the application forcefully closes.

## 4. Implementation Phases

* **Phase 1: Hardware ID & Security Engine**
  Write the `hardware.py` logic to successfully extract motherboard and MAC details. Write the `keygen.py` to generate the secure strings.
* **Phase 2: License Manager & Anti-Tamper**
  Write `license_manager.py` to handle the parsing and the SQL Server highest-date check.
* **Phase 3: User Interface**
  Build the `license_dialog.py` UI matching the Havano POS aesthetic.
* **Phase 4: Lockdown**
  Integrate the check into `main.py` and test the flow (Expired scenario, Wrong Machine scenario, Time-Travel scenario).

## 5. Next Steps
Once approved, we will begin with **Phase 1** and write `utils/hardware.py` and the `keygen.py` script.
