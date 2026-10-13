
"""Dependency helper for Lily's Windows 7 / Python 3.8 build."""
import platform, subprocess, sys

def main():
    if platform.system()!="Windows": print("This helper is intended for Windows.")
    if sys.version_info[:2] != (3,8): print("Recommended interpreter: Python 3.8.x")
    print("\nLily local mode uses llama.cpp + Qwen; no API key is required.")
    print("Install requirements-win7.txt, then make sure PyQt5 is available.")
    print("Optional extras (wake word, device pickers, remote dashboard) have their own files:")
    print("  requirements-optional.txt  requirements-audio-devices.txt  requirements-dashboard.txt")
    print("See INSTALL-WIN7.md section 3b before installing them.")
    try:
        subprocess.check_call([sys.executable,"-m","pip","install","-r","requirements-win7.txt"])
    except Exception as e: print("Dependency install was not completed:",e)
    print("\nThen run:  python Lily.py")
    print("Console:   python Lily.py --console")
if __name__=="__main__": main()
