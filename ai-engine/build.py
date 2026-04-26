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
        '--collect-all=flask',
        '--collect-all=flask_cors',
        '--collect-all=backports',
        '--collect-all=jaraco',
        '--hidden-import=mediapipe.python.solutions',
        '--hidden-import=matplotlib.pyplot',
        '--hidden-import=backports',
        '--hidden-import=backports.functools_lru_cache',
        '--hidden-import=jaraco.text',
        '--hidden-import=jaraco.context',
        '--hidden-import=jaraco.functools',
        '--exclude-module=torch',
        '--exclude-module=torchvision',
        '--exclude-module=torchaudio',
        '--exclude-module=tensorflow',
        '--exclude-module=jax',
        '--exclude-module=jaxlib',
        '--exclude-module=nvidia',
        '--exclude-module=scipy',
        '--exclude-module=pandas',
        '--log-level=INFO',
    ])
    print("Build complete!")
