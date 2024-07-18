import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if sys.version_info[0] < 3:
    print("!!! this script requires Python 3 - please check your Python environment and try again")
    sys.exit(1)

with open('requirements.txt') as f:
    packages = f.read().splitlines()
    for package in packages:
        install(package)

print("woohoo! all dependencies have been installed :)\n")