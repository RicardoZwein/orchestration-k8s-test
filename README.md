# Orchestration Tool (Exercise)

This side project was a hands-on exercise to get more familiar with container orchestration using Kubernetes (via Minikube) and interacting with an IBM Db2 database. Along the way, I set up database access via DBeaver, organized job metadata into its own SQL schema, and wrote scripts to export job results from Kubernetes to the local machine.

It also gave me the chance to brush up on PowerShell, Bash, and so on.

While definitely not production-grade, the system is functional and educational...It also could be a decent foundation for CI/CD and Prometheus & Grafana monitoring later on, if I feel like reworking it or you want to fork that for some reason.

---

## How to run it ?
**Note**: Designed for Windows (my local dev environment).

1. **Start services**
   Run `docker-compose` to spin up required containers.
   
2. **Set up Kubernetes**
   Launch Minikube and run `deploy_scheduler.ps1`.

3. **Trigger jobs**
   Manually trigger one of the defined CronJobs (they don’t run very often by default).

4. **Export job outputs**
   Use:

   ```powershell
   download_exports.ps1 -job <name> [-n <int>] [-localExportPath <path>]
   ```

5. **Sync or modify jobs**
   Use:

   ```powershell
   run_full_sync.ps1
   ```

   This will sync your current YAML job files into the cluster. It will also replace cron jobs and activate/deactivate jobs in db depending on whether the YAML jobs are in the jobs folder or not.

6. **Vibe out**
   Enjoy the therapeutic experience of watching a Kubernetes pipeline just work. Optional: play some lofi, fork this, and add some fun. If you're also a student, this might feel less overwhelming to fiddle with than large projects!


The only reason this is published at all is because my teachers usually tell me to add anything I make to my GitHub account, and I happened to have enough free time to do this. 

---

## ⚠️ Disclaimer

This was built on vacation as a personal learning tool. Some parts are quite messy, unsafe for production, or hardcoded. There are even some files left that likley are not of use anymore. I focused on understanding the tooling for now, not delivering production-ready infra, or cleaning up all my files. That said, feel free to dig in. 

Published mainly because my teachers tell me: *"Put everything on GitHub."* So... here we are. They likely expected a more professional voice, which I can definitely do at work...Or for a bigger public-facing project.

Take this as a piece of me having fun, which is quite different from how I would write at work - This really is just my personal space. Thank you for your understanding.
