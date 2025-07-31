FROM ibmcom/db2:11.5.8.0

ENV LICENSE=accept \
    DB2INST1_PASSWORD=passw0rd \
    DB2INST1=db2inst1 \
    DB2FENC1_PASSWORD=passw0rd \
    DB2FENC1=db2fenc1 \
    DBNAME=testdb

COPY init_job_mgmt.sql /database/config/
COPY init_public.sql /database/config/
COPY setup-db2.sh /database/config/setup-db2.sh
RUN chmod +x /database/config/setup-db2.sh