import PyInstaller.__main__
import sys

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'app.py',
        '--name=healthos-backend',
        '--onefile',
        '--noconsole',
        '--hidden-import=mediapipe',
        '--hidden-import=mediapipe.python.solutions',
        '--hidden-import=matplotlib',
        '--hidden-import=matplotlib.pyplot',
        '--collect-all=mediapipe',
        '--collect-all=matplotlib',
        '--log-level=INFO',
    ])
    print("Build complete!")
