import os
import ibm_db
import sys
import json
import yaml
from pathlib import Path
from scripts.jobfile_class import JobFile
from dotenv import load_dotenv
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException

load_dotenv()
JOBS_DIR = "jobs"
CONN_STR = os.getenv("CONN_STR")

# Init Kubernetes client
config.load_incluster_config()
batch_v1 = client.BatchV1Api()
api_client = client.ApiClient()

def get_db_job_names(conn) -> dict:
    job_map = {}
    stmt = ibm_db.exec_immediate(conn, "SELECT job_name, is_active FROM job_mgmt.jobs")
    while row := ibm_db.fetch_assoc(stmt):
        job_map[row["JOB_NAME"]] = row["IS_ACTIVE"]
    return job_map

def get_schedule_for_job(job_name):
    conn = ibm_db.connect(CONN_STR, "", "")
    stmt = ibm_db.prepare(conn, "SELECT schedule FROM job_mgmt.jobs WHERE job_name = ?")
    ibm_db.execute(stmt, (job_name,))
    row = ibm_db.fetch_assoc(stmt)
    ibm_db.close(conn)
    return row["SCHEDULE"] if row else "* * * * *"

def set_inactive_for_missing(conn, missing_jobs):
    if not missing_jobs:
        return
    for job_name in missing_jobs:
        stmt = ibm_db.prepare(conn, """
            UPDATE job_mgmt.jobs SET is_active = false WHERE job_name = ?
        """)
        ibm_db.execute(stmt, (job_name,))
        print(f"🛑 Marked '{job_name}' as inactive (missing from YAML folder)")

def set_active_jobs(conn, yaml_jobs):
    for job_name in yaml_jobs:
        stmt = ibm_db.prepare(conn, """
            UPDATE job_mgmt.jobs SET is_active = true WHERE job_name = ?
        """)
        ibm_db.execute(stmt, (job_name,))
        print(f"✅ Marked '{job_name}' as active")


def insert_missing_jobs(yaml_jobs, db_jobs):
    new_jobs = {
        job_file for job_file in yaml_jobs
        if job_file not in db_jobs
    }
    for job_file in new_jobs:
        full_path = os.path.join(JOBS_DIR, f"{job_file}.yaml")
        print(f"➕ Adding new job: {job_file}")
        try:
            result = os.popen(f"{sys.executable} sender.py {full_path}").read()
            print(f"✅ Successfully added job: {job_file}")
            if result:
                print(f"   Output: {result.strip()}")
        except Exception as e:
            print(f"❌ Failed to add job {job_file}: {e}")


def get_cronjob_names() -> set:
    try:
        cronjobs = batch_v1.list_namespaced_cron_job(namespace="default").items
        return {cj.metadata.name for cj in cronjobs}
    except Exception as e:
        print(f"❌ Failed to fetch CronJobs: {e}")
        return set()

def generate_cronjob_spec(job_name: str, schedule: str, yaml_path: str, suspend: bool = False):
    runner_image = os.getenv("RUNNER_IMAGE", "batch-runner:latest")
    return client.V1CronJob(
        api_version="batch/v1",
        kind="CronJob",
        metadata=client.V1ObjectMeta(
            name=(job_name),
            labels={"app": "batch-runner"},
        ),
        spec=client.V1CronJobSpec(
            schedule=schedule,
            suspend=suspend,
            job_template=client.V1JobTemplateSpec(
                spec=client.V1JobSpec(
                    template=client.V1PodTemplateSpec(
                        spec=client.V1PodSpec(
                            containers=[
                                client.V1Container(
                                    name="runner",
                                    image=runner_image,
                                    image_pull_policy="Never",
                                    command=["python", "runner.py", yaml_path],
                                    env=[
                                        client.V1EnvVar(
                                            name="CONN_STR",
                                            value_from=client.V1EnvVarSource(
                                                secret_key_ref=client.V1SecretKeySelector(
                                                    name="db-credentials",
                                                    key="conn_str"
                                                )
                                            )
                                        )
                                    ],
                                    volume_mounts=[client.V1VolumeMount(
                                        name="export-volume",
                                        mount_path="/app/data/exports"
                                    )]
                                )
                            ],
                            volumes=[client.V1Volume(
                                name="export-volume",
                                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                                    claim_name="job-exports-pvc"
                                )
                            )],
                            restart_policy="Never"
                        )
                    )
                )
            )
        )
    )

def sync_cronjobs_with_db(db_jobs):
    k8s_cronjobs = get_cronjob_names()
    print(f"📦 Existing K8s CronJobs: {sorted(k8s_cronjobs)}")

    db_names = set(db_jobs.keys())
    k8s_names = {(jn) for jn in db_names}
    print(f"🧾 Expected CronJob names: {sorted(k8s_names)}")

    to_create = db_names - k8s_cronjobs
    to_delete = k8s_cronjobs - db_names
    to_update = db_names & k8s_cronjobs

    for job in to_create:
        original_job_name = job.removeprefix("cronjob-")
        yaml_path = os.path.join(JOBS_DIR, f"{original_job_name}.yaml")
        if os.path.exists(yaml_path):
            print(f"⏳ Creating CronJob: {job}")
            try:
                schedule = get_schedule_for_job(original_job_name)
                cronjob_spec = generate_cronjob_spec(original_job_name, schedule, yaml_path)
                batch_v1.create_namespaced_cron_job(namespace="default", body=cronjob_spec)
                print(f"✅ Created CronJob: {job}")
            except ApiException as e:
                if e.status == 409:
                    print(f"⚠️ Already exists: {job}. Replacing instead.")
                    batch_v1.replace_namespaced_cron_job(name=job, namespace="default", body=cronjob_spec)
                    print(f"♻️ Replaced existing CronJob: {job}")
                else:
                    print(f"❌ Failed to create CronJob {job}: {e}")
        else:
            print(f"⚠️ CronJob YAML not found for DB job '{original_job_name}'")

    for job in to_delete:
        print(f"🗑️ Deleting orphaned CronJob: {job}")
        try:
            batch_v1.delete_namespaced_cron_job(name=job, namespace="default")
        except Exception as e:
            print(f"❌ Failed to delete CronJob {job}: {e}")

    for job in to_update:
        suspend = not db_jobs[job]
        print(f"🔄 Syncing suspend={suspend} for CronJob: {job}")
        try:
            body = {"spec": {"suspend": suspend}}
            batch_v1.patch_namespaced_cron_job(name=job, namespace="default", body=body)
        except Exception as e:
            print(f"❌ Failed to patch CronJob {job}: {e}")

def sync_all():
    if not CONN_STR:
        raise ValueError("CONN_STR not set in environment")

    print(f"📁 Looking for YAML files in: {os.path.abspath(JOBS_DIR)}")
    if not os.path.exists(JOBS_DIR):
        print(f"❌ Jobs directory '{JOBS_DIR}' not found")
        return

    job_files = [f for f in os.listdir(JOBS_DIR) if f.endswith(".yaml")]
    print(f"📄 Found {len(job_files)} YAML files: {job_files}")

    conn = ibm_db.connect(CONN_STR, "", "")
    yaml_jobs = {Path(f).stem for f in job_files}
    db_jobs = get_db_job_names(conn)

    print(f"🗂️  YAML jobs: {yaml_jobs}")
    print(f"💾 DB jobs: {db_jobs}")

    insert_missing_jobs(yaml_jobs, db_jobs)
    set_active_jobs(conn, yaml_jobs)
    set_inactive_for_missing(conn, {name for name in set(db_jobs.keys())} - yaml_jobs)

    db_jobs = get_db_job_names(conn)  # Refresh after inserts/updates
    sync_cronjobs_with_db(db_jobs)

    ibm_db.close(conn)

if __name__ == "__main__":
    print("🔁 Syncing job YAMLs with database records and Kubernetes...")
    try:
        sync_all()
        print("✅ Full sync completed successfully")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)