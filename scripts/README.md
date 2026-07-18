# Scripts

PowerShell helpers for local development.

Start infrastructure, the backend API, and the frontend:

```powershell
.\scripts\dev.ps1
```

On the first run, bootstrap migrations, seed data, Kafka, MinIO, and Keycloak:

```powershell
.\scripts\dev.ps1 -Bootstrap
```

Add `-Workers` to run the outbox publisher and all backend workers. The
frontend stays in the foreground; press `Ctrl+C` to stop it. Docker volumes
are preserved.
