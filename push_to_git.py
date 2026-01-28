#!/usr/bin/env python3
"""
Push application to Git repository
"""

import subprocess
import sys
from datetime import datetime

def run_command(cmd, description):
    """Run a git command and report results"""
    print(f"\n{'='*70}")
    print(f"📤 {description}")
    print(f"{'='*70}")
    print(f"Command: {cmd}")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=r"c:\Users\ramst\Documents\apps\tkfl_ocr\pt5",
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"✅ Success")
            if result.stdout:
                print(f"Output:\n{result.stdout[:500]}")
        else:
            print(f"❌ Error (Code: {result.returncode})")
            if result.stderr:
                print(f"Error:\n{result.stderr[:500]}")
        
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"⏱️  Timeout after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

def main():
    print("\n" + "="*70)
    print("🚀 GIT PUSH - TKFL OCR Application")
    print("="*70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Repository: https://github.com/adm-recens/tkfl-ocr-pt4.git")
    
    # Step 1: Check status
    success = run_command(
        "git status --short",
        "Step 1: Check git status"
    )
    
    if not success:
        print("\n⚠️  Warning: Could not check status, continuing...")
    
    # Step 2: Add all files
    success = run_command(
        "git add .",
        "Step 2: Stage all files"
    )
    
    if not success:
        print("\n❌ Failed to stage files")
        return False
    
    # Step 3: Create commit message
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    commit_msg = f"Update: Learning History Page + OCR Field Capture Analysis [{timestamp}]"
    
    print(f"\n📝 Commit Message: {commit_msg}")
    
    # Step 4: Commit
    success = run_command(
        f'git commit -m "{commit_msg}"',
        "Step 3: Create commit"
    )
    
    if not success:
        print("\n⚠️  Warning: Commit failed (may have nothing to commit)")
    
    # Step 5: Pull latest (in case of conflicts)
    success = run_command(
        "git pull origin main",
        "Step 4: Pull latest from remote"
    )
    
    if not success:
        print("\n⚠️  Warning: Pull failed")
    
    # Step 6: Push to remote
    success = run_command(
        "git push origin main",
        "Step 5: Push to remote repository"
    )
    
    if success:
        print("\n" + "="*70)
        print("✅ SUCCESS: Application pushed to Git!")
        print("="*70)
        print(f"Repository: https://github.com/adm-recens/tkfl-ocr-pt4")
        print(f"Branch: main")
        return True
    else:
        print("\n" + "="*70)
        print("❌ FAILED: Could not push to Git")
        print("="*70)
        print("\nPlease check:")
        print("1. Internet connection")
        print("2. Git credentials (may need to login via git credential manager)")
        print("3. Repository access permissions")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
