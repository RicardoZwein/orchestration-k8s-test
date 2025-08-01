from fastapi import FastAPI, Response
import os
import platform

if platform.system() == "Windows":
    dll_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../infra/db2_driver/clidriver/bin"))
    os.add_dll_directory(dll_path)

import ibm_db

app = FastAPI()

DB_CONN_STR = os.getenv("CONN_STR") or "DATABASE=testdb;HOSTNAME=localhost;PORT=50000;PROTOCOL=TCPIP;UID=db2inst1;PWD=passw0rd;"

@app.get("/metrics")
def get_metrics():
    try:
        conn = ibm_db.connect(DB_CONN_STR, "", "")
    except Exception as e:
        return Response(f"# DB connection failed: {e}", status_code=500)

    metrics = []

    try:
        # Confirm table exists
        stmt = ibm_db.exec_immediate(conn, """
            SELECT TABSCHEMA, TABNAME
            FROM SYSCAT.TABLES
            WHERE LOWER(TABNAME) = 'job_runs'
        """)
        while row := ibm_db.fetch_assoc(stmt):
            metrics.append(f'# Found table: {row["TABSCHEMA"]}.{row["TABNAME"]}')
    except Exception as e:
        return Response(f"# Table check failed: {e}", status_code=500)

    try:
        # Run counts by status
        for status in ["SUCCESS", "FAILURE"]:
            stmt = ibm_db.exec_immediate(conn, f"""
                SELECT job_id, COUNT(*) as count
                FROM job_mgmt.job_runs
                WHERE status = '{status}'
                GROUP BY job_id
            """)
            while row := ibm_db.fetch_assoc(stmt):
                metrics.append(
                    f'job_runs_total{{job_id="{row["JOB_ID"]}",status="{status.lower()}"}} {row["COUNT"]}'
                )
    except Exception as e:
        metrics.append(f"# Job count query failed: {e}")

    try:
        # Duration stats
        stmt = ibm_db.exec_immediate(conn, """
            SELECT job_id,
                MAX(BIGINT(DAYS(ENDED_AT)) * 86400 + MIDNIGHT_SECONDS(ENDED_AT) -
                    (BIGINT(DAYS(STARTED_AT)) * 86400 + MIDNIGHT_SECONDS(STARTED_AT))) AS max_duration,
                MIN(BIGINT(DAYS(ENDED_AT)) * 86400 + MIDNIGHT_SECONDS(ENDED_AT) -
                    (BIGINT(DAYS(STARTED_AT)) * 86400 + MIDNIGHT_SECONDS(STARTED_AT))) AS min_duration,
                AVG(DOUBLE(BIGINT(DAYS(ENDED_AT)) * 86400 + MIDNIGHT_SECONDS(ENDED_AT) -
                    (BIGINT(DAYS(STARTED_AT)) * 86400 + MIDNIGHT_SECONDS(STARTED_AT)))) AS avg_duration
            FROM "JOB_MGMT"."JOB_RUNS"
            WHERE STARTED_AT IS NOT NULL AND ENDED_AT IS NOT NULL
            GROUP BY job_id
        """)
        while row := ibm_db.fetch_assoc(stmt):
            metrics.append(f'job_duration_seconds_max{{job_id="{row["JOB_ID"]}"}} {row["MAX_DURATION"]}')
            metrics.append(f'job_duration_seconds_min{{job_id="{row["JOB_ID"]}"}} {row["MIN_DURATION"]}')
            metrics.append(f'job_duration_seconds_avg{{job_id="{row["JOB_ID"]}"}} {row["AVG_DURATION"]}')
    except Exception as e:
        metrics.append(f"# Duration stats query failed: {e}")

    try:
        # Last run status and timestamp
        stmt = ibm_db.exec_immediate(conn, """
            SELECT job_id, status,
                BIGINT(DAYS(ENDED_AT) - DAYS(DATE('1970-01-01'))) * 86400
                + MIDNIGHT_SECONDS(ENDED_AT) AS ended
            FROM (
                SELECT job_id, status, ended_at,
                    ROW_NUMBER() OVER (PARTITION BY job_id ORDER BY ended_at DESC) AS rn
                FROM "JOB_MGMT"."JOB_RUNS"
                WHERE ended_at IS NOT NULL
            ) sub
            WHERE rn = 1
        """)


        while row := ibm_db.fetch_assoc(stmt):
            status_value = 1 if row["STATUS"] == "SUCCESS" else 0
            metrics.append(f'job_last_status{{job_id="{row["JOB_ID"]}"}} {status_value}')
            metrics.append(f'job_run_timestamp{{job_id="{row["JOB_ID"]}"}} {row["ENDED"]}')
    except Exception as e:
        metrics.append(f"# Last status query failed: {e}")

    try:
        # Count of active (unfinished) runs
        stmt = ibm_db.exec_immediate(conn, """
            SELECT job_id, COUNT(*) AS active
            FROM "JOB_MGMT"."JOB_RUNS"
            WHERE ENDED_AT IS NULL
            GROUP BY job_id
        """)
        while row := ibm_db.fetch_assoc(stmt):
            metrics.append(f'job_active_count{{job_id="{row["JOB_ID"]}"}} {row["ACTIVE"]}')
    except Exception as e:
        metrics.append(f"# Active job query failed: {e}")

    ibm_db.close(conn)
    return Response("\n".join(metrics), media_type="text/plain")