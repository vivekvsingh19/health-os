import PyInstaller.__main__
import sys

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'app.py',
        '--name=healthos-backend',
        '--onefile',
        '--noconsole',
        '--collect-all=mediapipe',
        '--collect-all=matplotlib',
    ])
    print("Build complete!")
