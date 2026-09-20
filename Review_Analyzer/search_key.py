import os

def search_key():
    key = "AQ.Ab8RN6KTjqJJL77T2IMsdyMluGrkyc8WFKlcLC9p0uFVuHuY-Q"
    found = []
    
    for root, dirs, files in os.walk("."):
        if ".git" in root or "__pycache__" in root or ".pytest_cache" in root:
            continue
            
        for file in files:
            filepath = os.path.join(root, file)
            # Skip some binaries/images
            if filepath.endswith(".png") or filepath.endswith(".jpg") or filepath.endswith(".pyc"):
                continue
                
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    if key in content:
                        found.append(filepath)
            except Exception:
                pass
                
    for f in found:
        print(f"Found in: {f}")

if __name__ == "__main__":
    search_key()
