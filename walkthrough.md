# Walkthrough - Web Smart Switch Support

## Changes Implemented

### 1. New Protocol Support
- Added **Web Smart** option in the "Add Switch" dialog.
- Default port set to **80** when Web Smart is selected.
- Backend uses `http` as the protocol identifier.

### 2. WebSmartClient (`app/net/web_smart_client.py`)
- Implemented a new client class using `requests`.
- Logic includes:
    - **Login**: Tries multiple common endpoints (`/login.cgi`, `/logon.htm`, Basic Auth).
    - **Download**: Tries common backup endpoints (`config.bin`, `backup.cgi`, etc.).
    - **Session Management**: Maintains cookies using `requests.Session`.

### 3. Backup Runner Integration
- Updated `BackupRunner` to route `http`/`websmart` protocol to the new client.
- Added error handling specific to HTTP connection issues.

## Verification Steps

### 1. Install Dependencies
You must install the new dependencies first:
```powershell
pip install -r requirements.txt
```

### 2. Add a Web Smart Switch
1.  Open the application.
2.  Go to **Inventory** > **Add Switch**.
3.  Enter Name and IP.
4.  Select **Web Smart** protocol (Port should auto-change to 80).
5.  Select Credentials.
6.  Click **Save**.

### 3. Test Backup
1.  Select the newly added switch in the table.
2.  Click **Get Data**.
3.  Watch the "Backup Console" on the right.
    - It should show "Connecting via http..."
    - Then "Login successful..."
    - And finally "Config downloaded successfully".

### 4. Troubleshooting
If the backup fails with "Could not find a valid configuration download endpoint":
- The switch model might use a different URL than the standard ones (GS950/FS750).
- Check the switch's web interface URL manually in a browser.
- Let me know the specific URL so I can add it to `WebSmartClient`.
