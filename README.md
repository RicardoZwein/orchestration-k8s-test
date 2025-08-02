# Orchestration Tool (Exercise)

This side project was a hands-on exercise to get more familiar with container orchestration using **Kubernetes** (via **Minikube**) and interacting with an **IBM Db2** database. Along the way, I set up database access via **DBeaver**, organized job metadata into its own SQL schema, and wrote scripts to export job results from Kubernetes to the local machine.

It also gave me the chance to brush up on PowerShell, Bash, and so on.

While definitely not production-grade, the system is functional and educational. It could even be a decent foundation for CI/CD, or a Grafana Dashboard - if I feel like reworking it, or *you* want to fork that for some reason.

---

## How to run it?

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

### Extra :
You can now run Prometheus and Grafana! Just cd your way into `Prometheus/` and call `start_exporter.ps1`, then `docker compose up --build`. Just make sure ports 9123, 3333, and 9090 are free. Otherwise, still inside Prometheus/, please do change the used ports for  `start_exporter.ps1` and/or `docker-compose.yml` in said files' content. There is no Grafana dashboard set up (yet?) though.

   This will sync your current YAML job files into the cluster.
   It also replaces existing CronJobs and updates job activation based on whether the YAMLs are present in the `jobs/` folder.

6. **Vibe out**
   Enjoy the therapeutic experience of watching a Kubernetes pipeline just work.
   Optional: play some lofi, fork this, and add some fun.
   If you're also a student, this might feel less overwhelming to fiddle with than large projects!

---

The only reason this is published at all is because my teachers usually tell me to add anything I make to my GitHub account and I happened to have enough free time to do this.

---

## ⚠️ Disclaimer

This was built on vacation as a personal learning tool.
Some parts are quite messy, hardcoded, or unsafe for production.
There are even some leftover files that probably aren’t useful anymore.
I focused on understanding the tooling, not delivering production-ready infra or cleaning up everything.

That said, feel free to dig in.

Published mainly because my teachers tell me: *"Put everything on GitHub."*
So... here we are. They probably expected a more professional voice, which I can absolutely do at work or for a bigger public-facing project.

Take this as a piece of me having fun, which is very different from how I write at work.
This really is just my personal space. Thanks for your understanding.
