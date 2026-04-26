import PyInstaller.__main__
import sys

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'app.py',
        '--name=healthos-backend',
        '--onefile',
        '--noconsole',
        '--hidden-import=mediapipe',
        '--hidden-import=cv2',
        '--hidden-import=flask',
        '--hidden-import=flask_cors',
        '--hidden-import=backports',
        '--hidden-import=backports.functools_lru_cache',
        '--hidden-import=jaraco.text',
        '--hidden-import=jaraco.context',
        '--hidden-import=jaraco.functools',
        '--hidden-import=pkg_resources',
        '--collect-all=mediapipe',
        '--collect-all=jaraco',
        '--collect-all=backports',
        # Exclude huge unused ML frameworks that mediapipe drags in
        '--exclude-module=torch',
        '--exclude-module=torchvision',
        '--exclude-module=torchaudio',
        '--exclude-module=triton',
        '--exclude-module=jax',
        '--exclude-module=jaxlib',
        '--exclude-module=tensorflow',
        '--exclude-module=tensorboard',
        '--exclude-module=keras',
        '--exclude-module=scipy',
        '--exclude-module=sklearn',
        '--exclude-module=pandas',
        '--exclude-module=IPython',
        '--exclude-module=jupyter',
        '--log-level=INFO',
    ])
    print("Build complete!")
