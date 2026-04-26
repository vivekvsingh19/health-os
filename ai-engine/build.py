import PyInstaller.__main__
import os
import sys
import mediapipe
import matplotlib

# Find base paths
mp_base = os.path.dirname(mediapipe.__file__)
mpl_base = os.path.dirname(matplotlib.__file__)

if __name__ == '__main__':
    PyInstaller.__main__.run([
        'app.py',
        '--name=healthos-backend',
        '--onefile',
        '--noconsole',
        # Force inclusion of both package directories to be safe
        '--add-data', f'{mp_base}:mediapipe',
        '--add-data', f'{mpl_base}:matplotlib',
        # Standard collection
        '--collect-all', 'mediapipe',
        '--collect-all', 'matplotlib',
        # Hidden imports for critical submodules
        '--hidden-import', 'mediapipe.python.solutions.pose',
        '--hidden-import', 'mediapipe.python.solutions.drawing_utils',
        '--hidden-import', 'matplotlib.pyplot',
        # Exclusions to keep size reasonable
        '--exclude-module', 'torch',
        '--exclude-module', 'torchvision',
        '--exclude-module', 'jax',
        '--exclude-module', 'tensorflow',
        '--log-level', 'INFO',
    ])
    print("Build complete!")
