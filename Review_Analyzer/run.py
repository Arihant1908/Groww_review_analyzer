import sys
import os
import shutil
import subprocess

def main():
    stages = [
        {"name": "Import", "desc": "importing", "script": "src/importer.py"},
        {"name": "Redact", "desc": "redacting", "script": "src/redactor.py"},
        {"name": "Group", "desc": "grouping", "script": "src/themer.py"},
        {"name": "Numbers", "desc": "crunching numbers", "script": "src/analytics.py"},
        {"name": "Note", "desc": "writing the weekly note", "script": "src/note_writer.py"},
        {"name": "Email", "desc": "generating email drafts", "script": "src/emailer.py"},
    ]
    
    out_dir = "out"
    backup_dir = "out_backup_run"
    
    # Backup out dir
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
        
    if os.path.exists(out_dir):
        shutil.copytree(out_dir, backup_dir)
    else:
        os.makedirs(out_dir, exist_ok=True)
        
    try:
        raw_data = None
        if not sys.stdin.isatty():
            raw_data = sys.stdin.read()
            
        env = os.environ.copy()
        env["PYTHONPATH"] = os.path.abspath(".")
        
        for i, stage in enumerate(stages):
            print(f"Stage {i+1} of {len(stages)}: {stage['desc']}...")
            
            kwargs = {
                "capture_output": True,
                "text": True,
                "env": env
            }
            if i == 0 and raw_data:
                kwargs["input"] = raw_data
                
            result = subprocess.run(
                [sys.executable, stage['script']],
                **kwargs
            )
            
            if result.returncode != 0:
                print(f"\nError: Stage {i+1} ({stage['name']}) failed.")
                print(f"Explanation:\n{result.stderr.strip() or result.stdout.strip()}")
                
                # Restore backup
                if os.path.exists(out_dir):
                    shutil.rmtree(out_dir)
                if os.path.exists(backup_dir):
                    shutil.copytree(backup_dir, out_dir)
                else:
                    os.makedirs(out_dir)
                print("Output directory has been restored to its previous state. No partial overwrites occurred.")
                sys.exit(1)
                
            # If the note writer says "used AI layer" or "template used", print it
            if stage['name'] == 'Note':
                if 'Note written by model' in result.stdout:
                    print("  -> used AI layer")
                elif 'template used' in result.stdout:
                    print("  -> used template fallback")
            elif stage['name'] == 'Group':
                if 'Layer A' in result.stdout:
                    print("  -> used AI layer")
                elif 'Layer B' in result.stdout:
                    print("  -> used keyword fallback layer")
                    
        # Success!
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)
        print("All stages completed successfully!")
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Restoring outputs...")
        if os.path.exists(out_dir):
            shutil.rmtree(out_dir)
        if os.path.exists(backup_dir):
            shutil.copytree(backup_dir, out_dir)
        print("Output directory has been restored.")
        sys.exit(1)

if __name__ == "__main__":
    main()
