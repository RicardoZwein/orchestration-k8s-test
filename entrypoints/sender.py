import os
import sys
from pathlib import Path


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)


from scripts.jobfile_class import JobFile


file = Path(sys.argv[1])
if file.exists():
    print(f"Registering job: {file.name}")
    job = JobFile(str(file))
    print(f"✅ Registered {job.job_name}\n")
else:
    print(f"❌ File not found: {file}")
sys.exit(0)