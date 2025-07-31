import ibm_db
import subprocess
import os
import tempfile
from dotenv import load_dotenv

print("🔥🔥 FRESH IMAGE TEST 🔥🔥")

load_dotenv()
runner_image = os.getenv("RUNNER_IMAGE", "batch-runner:latest")

def k8s_cron_name(job_name: str) -> str:
    return f"cronjob-{job_name.lower().replace('_', '-')}"[:52]  # K8s name limit

def sync_cronjobs_from_db():
    conn_str = os.getenv("CONN_STR")
    if not conn_str:
        raise ValueError("CONN_STR environment variable is not set")

    try:
        conn = ibm_db.connect(conn_str, "", "")
    except Exception as e:
        raise RuntimeError(f"Failed to connect to DB2: {e}")

    stmt = ibm_db.exec_immediate(conn, """
        SELECT job_name, schedule, is_active
        FROM job_mgmt.jobs
    """)

    active_cronjobs = set()
    all_cronjobs_from_db = set()

    while (row := ibm_db.fetch_assoc(stmt)):
        job_name = row["JOB_NAME"]
        cron_expr = row["SCHEDULE"]
        is_active = row["IS_ACTIVE"]
        cronjob_name = k8s_cron_name(job_name)
        all_cronjobs_from_db.add(cronjob_name)

        yaml_path = f"jobs/{job_name}.yaml"

        if is_active:
            if not os.path.exists(yaml_path):
                print(f"⚠️  Skipping active job '{job_name}': Missing YAML file at {yaml_path}")
                continue

            active_cronjobs.add(cronjob_name)

            cron_yaml = f"""apiVersion: batch/v1
kind: CronJob
metadata:
  name: {cronjob_name}
  labels:
    app: batch-runner
spec:
  schedule: "{cron_expr}"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: runner
            image: {runner_image}
            imagePullPolicy: Never
            command: ["python", "runner.py", "{yaml_path}"]
            env:
            - name: CONN_STR
              valueFrom:
                secretKeyRef:
                  name: db-credentials
                  key: conn_str
            volumeMounts:
            - name: export-volume
              mountPath: /app/data/exports
          volumes:
          - name: export-volume
            persistentVolumeClaim:
              claimName: job-exports-pvc
          restartPolicy: Never
"""

            print(f"\n🔥 Applying CronJob: {cronjob_name}")
            print("────────────────────────────────────")
            print(cron_yaml.strip())
            print("────────────────────────────────────")

            with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yaml") as tmp:
                tmp.write(cron_yaml)
                tmp.flush()
                subprocess.run(["kubectl", "replace", "--force", "-f", tmp.name], check=False)

        else:
            print(f"🛑 Marked inactive in DB: {cronjob_name}")

    # Cleanup orphaned CronJobs
    kubectl_output = subprocess.check_output([
        "kubectl", "get", "cronjobs", "-l", "app=batch-runner", "-o", "jsonpath={.items[*].metadata.name}"
    ]).decode("utf-8")
    existing_cronjobs = set(kubectl_output.strip().split())

    for name in existing_cronjobs:
        if name not in active_cronjobs:
            print(f"🗑️ Deleting disabled or orphaned CronJob: {name}")
            subprocess.run(["kubectl", "delete", "cronjob", name], check=True)

    ibm_db.close(conn)

if __name__ == "__main__":
    sync_cronjobs_from_db()