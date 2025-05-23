# scripts/run_tests.py
"""Script to run tests with coverage."""

import subprocess
import sys

def run_tests():
    """Run tests with coverage reporting."""
    try:
        # Install test dependencies
        subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "pytest", "pytest-asyncio", "pytest-cov", "httpx"
        ], check=True)
        
        # Run tests with coverage
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "--cov=.", 
            "--cov-report=html",
            "--cov-report=term",
            "-v"
        ], check=False)
        
        return result.returncode
        
    except subprocess.CalledProcessError as e:
        print(f"Error running tests: {e}")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code)