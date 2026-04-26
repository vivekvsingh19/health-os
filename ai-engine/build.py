import PyInstaller.__main__
import os
import sys

if __name__ == '__main__':
    # Ensure model exists
    if not os.path.exists("pose_landmarker.task"):
        print("Error: pose_landmarker.task not found in current directory.")
        sys.exit(1)

    PyInstaller.__main__.run([
        'app.py',
        '--name=healthos-backend',
        '--onefile',
        '--noconsole',
        '--add-data', 'pose_landmarker.task:.',
        '--collect-all', 'mediapipe',
        '--collect-all', 'matplotlib',
        '--hidden-import', 'mediapipe.tasks.python.vision',
        '--hidden-import', 'matplotlib.pyplot',
        '--exclude-module', 'torch',
        '--exclude-module', 'torchvision',
        '--exclude-module', 'jax',
        '--exclude-module', 'tensorflow',
        '--log-level', 'INFO',
    ])
    print("Build complete!")
