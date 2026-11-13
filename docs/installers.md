# Desktop installers (Windows and macOS)

This guide explains how to build MangueTREE as a local desktop application for Windows and macOS. Users of the built application do not need Python or an internet connection. Everything runs on the user's machine, including the PDF reports.

Native applications must be built on the target system: a Windows `.exe` is built on Windows and a macOS `.app` on macOS. There are two ways to do it.

## Option 1: GitHub Actions (builds both)

The workflow `.github/workflows/build-desktop.yml` builds both applications on GitHub servers. It does not publish the app on the internet; it only uses GitHub as the build machine, and the repository can be private.

1. Push the repository to GitHub.
2. Open the **Actions** tab, select **Build MangueTREE (desktop)** and click **Run workflow**.
3. After about 10 minutes, download the artifacts from the run page: `MangueTREE-Windows.zip` and `MangueTREE-macOS.zip`.

When you push a tag that starts with `v` (for example `v1.0.0`), the workflow also creates a GitHub Release with both files attached.

## Option 2: Local build

The machine that builds needs Python 3.11 or newer. The built application does not.

### Windows

1. Install Python 3.11 or newer from python.org (select "Add Python to PATH").
2. From the repository root, run `build_windows.bat` (double-click or run it in a terminal).
3. The output is `dist\MangueTREE\MangueTREE.exe`. Zip the folder `dist\MangueTREE` to share it.

### macOS

1. Install Python 3.11 or newer (python.org or `brew install python@3.11`).
2. From the repository root, run `bash build_macos.command`.
3. The output is `dist/MangueTREE.app`. Zip the `.app` to share it.

Both scripts run `pip install -r requirements.txt pyinstaller`, `pip install --no-deps .` and `pyinstaller MangueTREE.spec`.

## Using the application

### Windows

1. Unzip the file and open the folder.
2. Double-click `MangueTREE.exe`.
3. The first time, Windows may show a SmartScreen warning because the application is not signed. Click "More info" and then "Run anyway".
4. After a few seconds the app opens in the browser at `http://localhost:8501`.

### macOS

1. Unzip the file and, if you wish, drag `MangueTREE.app` to Applications.
2. The first time, right-click the app, choose Open, and confirm. macOS blocks unsigned applications by default; opening it this way once makes it trusted.
3. The app opens in the browser at `http://localhost:8501`.

To quit, click **Quit MangueTREE** in the sidebar of the Home or About page. The application has no console window, and the button stops the local server; after it, you can close the browser tab. (The button appears only in the packaged application and when started with `python -m manguetree.launcher`; the plain `streamlit run` does not show it.)

## Notes

- The applications are not code-signed, so the SmartScreen and Gatekeeper warnings are expected. Code signing is left for a future version.
- Antivirus programs can rarely flag applications packaged with PyInstaller as false positives.
- The first start is slower because the application unpacks its environment.
- Each application is about 300 to 500 MB because it bundles Python and the libraries.
