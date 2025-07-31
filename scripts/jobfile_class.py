import time
import csv
import polars as pl
from yaml import safe_load
from dotenv import load_dotenv
import os
import platform

driver_path = os.getenv("DB2_DRIVER_PATH")
if driver_path and platform.system() == "Windows":
    os.add_dll_directory(driver_path)


from scripts.color_classes import bcolors

import ibm_db

load_dotenv()
conn_str = os.getenv("CONN_STR")
REQUIRED_FIELDS = {"job_name", "type", "query", "output"}

class JobFile:
    def __init__(self, yaml_path):
        self.run_id = None
        with open(yaml_path, 'r') as f:
            self._data = safe_load(f)

        missing = REQUIRED_FIELDS - self._data.keys()
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        if "notify" not in self._data:
            self.log(f"Notify not found. Defaulting to `false`. Please define it explicitly.", "warning")
            self._data["notify"] = False


        if "schedule" not in self._data:
            self.schedule = None
        else:
            self.schedule = self._data["schedule"]

        for key, value in self._data.items():
            setattr(self, key, value)

        self.start_time = None
        self.end_time = None
        
        
        self.is_active = self._data.get("is_active", True)
        self.created_at = self._data.get("created_at", time.strftime("%Y-%m-%d %H:%M:%S"))

        self.insert_job()

        self.status = "PENDING"

    def set_status(self, status, conn_str=conn_str):
        conn = ibm_db.connect(conn_str, '', '')
        job_id = self.get_id()

        # Ensure timestamp formatting
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time)) if self.start_time else None
        end_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time)) if self.end_time else None

        if not hasattr(self, 'run_id') or self.run_id is None:
            insert_stmt = ibm_db.prepare(conn,
                "INSERT INTO job_mgmt.job_runs (job_id, started_at, ended_at, status) VALUES (?, ?, ?, ?)"
            )
            ibm_db.execute(insert_stmt, (job_id, start_time, end_time, status))

            # Retrieve the last inserted run_id
            id_stmt = ibm_db.exec_immediate(conn, "SELECT IDENTITY_VAL_LOCAL() FROM sysibm.sysdummy1")
            row = ibm_db.fetch_assoc(id_stmt)
            self.run_id = row["1"]

        else:
            update_stmt = ibm_db.prepare(conn,
                "UPDATE job_mgmt.job_runs SET job_id = ?, started_at = ?, ended_at = ?, status = ? WHERE run_id = ?"
            )
            ibm_db.execute(update_stmt, (job_id, start_time, end_time, status, self.run_id))

        self.status = status

        if conn:
            ibm_db.close(conn)

    def get_id(self, conn_str=conn_str):
        conn = ibm_db.connect(conn_str, '', '')
        stmt = "SELECT job_id FROM job_mgmt.jobs WHERE job_name = ?"
        stmt_prepared = ibm_db.prepare(conn, stmt)
        ibm_db.execute(stmt_prepared, (self.job_name,))
        result = ibm_db.fetch_assoc(stmt_prepared)

        if result:
            job_id = result['JOB_ID']
        else:
            job_id = None
        
        if conn:
            ibm_db.close(conn)
        
        return job_id

    def insert_job(self, conn_str=conn_str):
        conn = ibm_db.connect(conn_str, '', '')

        job_id = self.get_id()

        # If job doesn't exist, insert it
        if job_id is None:
            insert_stmt = ibm_db.prepare(conn,
                "INSERT INTO job_mgmt.jobs (job_name, schedule, is_active, created_at) VALUES (?, ?, ?, ?)"
            )
            ibm_db.execute(insert_stmt, (self.job_name, self.schedule, self.is_active, self.created_at))

            self.log(f"Successfully inserted job '{self.job_name}' into the database.")
        else:
            self.set_status(None)
            self.log(f"Warning: No job inserted : {self.job_name} already exists under id {job_id}.", "warning")

        if conn:
            ibm_db.close(conn)

    def log(self, log_message, type="normal", debug=True,conn_str=conn_str):
        
        if type == "fail":
            print(f"\n{bcolors.FAIL} {log_message} {bcolors.ENDC}\n")
        elif type == "warning":
            print(f"\n{bcolors.WARNING} {log_message} {bcolors.ENDC}\n")
        else:
            print(f"\n{log_message}\n")

        run_id = self.run_id
        conn = ibm_db.connect(conn_str, '', '')
        log_stmt = ibm_db.prepare(conn,
            "INSERT INTO job_mgmt.job_logs (run_id, log_time, message) VALUES (?, ?, ?)"
        )

        log_time = time.strftime("%Y-%m-%d %H:%M:%S")

        if debug:
            print(f"run_id : {self.run_id}")
            print(f"log_time : {log_time}")
            print(f"message : {log_message}")


        ibm_db.execute(log_stmt, (run_id,log_time,log_message))

        if conn:
            ibm_db.close(conn)

    def run(self, conn_str=conn_str,  output_dir="/app/data/exports"):
        self.start_time = time.time()
        start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.start_time))
        self.set_status("RUNNING")
        self.log(f"Started Running job {self.job_name} at {start_time}")

        is_successful = False
        conn = None

        try:
            conn = ibm_db.connect(conn_str, '', '')
            stmt = ibm_db.exec_immediate(conn, self.query)

            rows = []
            header = [ibm_db.field_name(stmt, i) for i in range(ibm_db.num_fields(stmt))]

            row = ibm_db.fetch_assoc(stmt)
            while row:
                rows.append(row)
                row = ibm_db.fetch_assoc(stmt)

            # Convert to Polars DataFrame and preview
            try:
                df = pl.DataFrame(rows)
                print(f"{bcolors.OKCYAN}Result Preview (Polars DataFrame):{bcolors.ENDC}")
                print(df.head(10))
            except Exception as df_err:
                print(f"{bcolors.WARNING}Could not display DataFrame preview: {df_err}{bcolors.ENDC}")

            # Write to CSV
            output_path = f"{output_dir}/{self.output}"
            with open(output_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=header)
                writer.writeheader()
                writer.writerows(rows)

            is_successful = True

        except Exception as e:
            self.log(f"Error: {e}", "fail")
            is_successful = False

        finally:
            self.end_time = time.time()
            if is_successful == True:
                self.set_status("SUCCESS") 
            else:
                self.set_status("FAILURE")

            readable_end = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.end_time))
            self.log(f"Job Ended with Status: {self.status} at time: {readable_end}")
            

            if conn:
                ibm_db.close(conn)

    def duration(self):
        if self.start_time and self.end_time:
            return round(self.end_time - self.start_time, 2)
        return None

    def __repr__(self):
        return f"<JobFile {self.job_name} | status={self.status}>"