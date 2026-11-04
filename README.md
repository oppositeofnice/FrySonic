# FrySonic
Small Windows tray app that switches between two selected devices with a single click

Download

Get FrySonic.exe from the Releases page and run it. No Python needed. Windows may show a SmartScreen warning because the exe isn't signed. Click "More info", then "Run anyway".

Usage

On first launch a setup window opens where you pick the two devices. After that, just click the tray icon to switch. Right-click it for settings, "Start With Windows" and exit.

Notes
Switching is done with the AudioDeviceCmdlets PowerShell module. If it's missing, FrySonic installs it for your user on first launch (this also marks PSGallery as a trusted repository).
Devices are saved by index, so if you plug in or remove audio devices you might have to pick them again in Settings.
Windows only.
Run from source
pip install -r requirements.txt
pythonw FrySonic.pyw

Settings are saved in %APPDATA%\FrySonic.
