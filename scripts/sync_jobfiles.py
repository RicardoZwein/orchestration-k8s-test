import os
import ibm_db
import subprocess
import sys
from pathlib import Path
from scripts.jobfile_class import JobFile
from dotenv import load_dotenv

load_dotenv()
JOBS_DIR = "jobs"
CONN_STR = os.getenv("CONN_STR")

def get_db_job_names(conn) -> set:
    job_names = set()
    stmt = ibm_db.exec_immediate(conn, "SELECT job_name FROM job_mgmt.jobs")
    while row := ibm_db.fetch_assoc(stmt):
        job_names.add(row["JOB_NAME"])
    return job_names

def set_inactive_for_missing(conn, missing_jobs):
    if not missing_jobs:
        return
    for job_name in missing_jobs:
        stmt = ibm_db.prepare(conn, """
            UPDATE job_mgmt.jobs SET is_active = false WHERE job_name = ?
        """)
        ibm_db.execute(stmt, (job_name,))
        print(f"🛑 Marked '{job_name}' as inactive (missing from YAML folder)")

def insert_missing_jobs(yaml_jobs, db_jobs):
    new_jobs = yaml_jobs - db_jobs
    for job_file in new_jobs:
        full_path = os.path.join(JOBS_DIR, f"{job_file}.yaml")
        print(f"➕ Adding new job: {job_file}")
        
        # Use subprocess instead of os.system for better control and error handling
        try:
            # Try using the current Python interpreter
            result = subprocess.run(
                [sys.executable, "sender.py", full_path],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✅ Successfully added job: {job_file}")
            if result.stdout:
                print(f"   Output: {result.stdout.strip()}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to add job {job_file}: {e}")
            if e.stdout:
                print(f"   Stdout: {e.stdout}")
            if e.stderr:
                print(f"   Stderr: {e.stderr}")
        except FileNotFoundError:
            print(f"❌ sender.py not found for job {job_file}")

def sync_all():
    if not CONN_STR:
        raise ValueError("CONN_STR not set in environment")

    print(f"📁 Looking for YAML files in: {os.path.abspath(JOBS_DIR)}")
    
    # Check if jobs directory exists
    if not os.path.exists(JOBS_DIR):
        print(f"❌ Jobs directory '{JOBS_DIR}' not found")
        return
    
    # List files in jobs directory for debugging
    job_files = [f for f in os.listdir(JOBS_DIR) if f.endswith(".yaml")]
    print(f"📄 Found {len(job_files)} YAML files: {job_files}")

    conn = ibm_db.connect(CONN_STR, "", "")
    yaml_jobs = {Path(f).stem for f in job_files}
    db_jobs = get_db_job_names(conn)
    
    print(f"🗂️  YAML jobs: {yaml_jobs}")
    print(f"💾 DB jobs: {db_jobs}")

    insert_missing_jobs(yaml_jobs, db_jobs)
    set_inactive_for_missing(conn, db_jobs - yaml_jobs)

    ibm_db.close(conn)

if __name__ == "__main__":
    print("🔁 Syncing job YAMLs with database records...")
    try:
        sync_all()
        print("✅ Sync completed successfully")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)