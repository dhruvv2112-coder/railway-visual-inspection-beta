OnTrack.AI laptop server (draft 1)
==================================

1. Unzip this folder anywhere (for example Documents\OnTrack-Server). Keep the laptop plugged in.
2. Double-click Start-OnTrack.bat.
   First run only: it installs Python 3.11 and the server (3-6 minutes, needs internet), asks you to
   create a patroller account and a reviewer (SSE) account, and asks Windows once to let phones on
   your Wi-Fi reach the laptop. A desktop shortcut "OnTrack.AI Server" is added.
3. The connect page opens in the browser:
   - Scan the first QR code with the phone camera to download and install the app.
   - Open the app on the same Wi-Fi. It finds the laptop by itself ("Find server").
     If not, type the address shown on the connect page, e.g. http://192.168.1.20:8000/
4. Sign in on the phone with the patroller ID and PIN, and start a patrol.
5. Review reports on the laptop at http://localhost:8000/ohe/review (sign in as the SSE).

Stop the server: close its window. Start again: the desktop shortcut.
Add more people: double-click Add-User.bat.
Your data (database, photos, accounts) is kept in %LOCALAPPDATA%\OnTrack and survives updates:
to update, unzip a newer package over this folder and start again.

If phones cannot connect:
- Phone and laptop must be on the same Wi-Fi (or the phone on the laptop's mobile hotspot).
- Windows: Settings > Network & internet > Wi-Fi > your network > set "Private network".
- Office Wi-Fi sometimes blocks devices from seeing each other; use the laptop's mobile hotspot instead.
