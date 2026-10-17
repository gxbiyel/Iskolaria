# Iskolaria

**A Containerized Scholarship Application System with an Automated Docker and Jenkins CI/CD Pipeline**

Course/Section: ITE302 (System Architecture and Integration, CTSYSINL) | Group: **Team Ka Ba?**

---

## Project Description

Iskolaria is a web-based scholarship management system. Students can browse open scholarships, check their eligibility, upload the required documents, and submit an application in one place. Scholarship officers use a separate review board to create and close scholarships, go through applications, verify or flag uploaded documents, and set each application to *under review*, *waitlisted*, *approved*, *rejected*, or *removed*. A student can cancel an application that is still pending, and every status change produces an in-app notification for the student.

The system is split into modules, each running in its own Docker container:

| Module | Technology | Responsibility |
| --- | --- | --- |
| `proxy` | Nginx 1.27 | Single public entry point (port 8080). Serves pages from the frontend and routes `/api/*` to the matching service. |
| `frontend` | Static HTML/CSS/JS on Nginx | Pages for students and admins: scholarship list, register, login, apply, my applications, review board. |
| `auth-service` | Python 3.12, FastAPI | Registration (checked against the school's student records), login, JWT issuing (HS256, 1 hour), bcrypt password hashing, admin seeding. |
| `scholarship-api` | Python 3.12, FastAPI | Scholarship catalog (requirements, deadlines, slots) and the eligibility check. |
| `application-api` | Node.js 20, Express | Application submission, review workflow, cancellation, slot accounting, notification history, summary report. |
| `upload-service` | Python 3.12, FastAPI | Document upload (PDF/JPG/PNG, max 2 MB, type checked by file signature), admin verify/flag, protected downloads. |
| `worker` | Python 3.12 | Reads status-change jobs from a Redis queue and saves notifications to the database. Includes a dead-letter list and crash recovery. |
| `db` | PostgreSQL 16 | Persistent data in the `pg-data` volume. Reachable only from the backend network. |
| `redis` | Redis 7 | Queue between `application-api` and `worker`. Not exposed to the host. |
| Jenkins (separate compose) | Jenkins LTS (JDK 17) + Docker CLI | CI/CD pipeline: Checkout → Test → Build Images → Deploy → Smoke Test, with results sent to Discord. |

**CI/CD summary.** The pipeline is defined in the `Jenkinsfile` stored in this repository. A failing test stops the pipeline so broken code never reaches deployment. Images are tagged with the Jenkins build number, so any earlier build can be redeployed (rollback) without losing data, because the database and uploaded files live in named volumes.

---

## Architecture Diagram

![Iskolaria architecture diagram](docs/architecture.png)

**Networks and ports**

- Only port **8080** (proxy) is published for the application. All other services are reachable only inside Docker.
- `frontend-net`: proxy, frontend, and the four APIs. `backend-net`: the four APIs, worker, db, and redis. The proxy cannot reach the database or Redis directly.
- Volumes: `pg-data` (PostgreSQL), `uploads-data` (uploaded documents, mounted at `/data/uploads`), `jenkins_home` (Jenkins data).

---

## Prerequisites

- **Docker Engine** and **Docker Compose v2** (the `docker compose` command, not `docker-compose`)
- **Git**
- Free ports on the host: **8080** (application), **8081** (Jenkins UI), **50000** (Jenkins agents)
- Access to the host's Docker socket (`/var/run/docker.sock`); Jenkins uses it to build and deploy. This is a lab-only setup.
- A **GitHub repository** containing this project (for the Jenkins pipeline)
- A **Discord webhook URL** (optional, for build notifications)
- A real **`.env` file** created from `.env.example`

---

## How to Start Jenkins and the Stack

### 1. Clone the repository

```bash
git clone https://github.com/gxbiyel/Iskolaria.git
cd Iskolaria
```

### 2. Start Jenkins (separate compose project)

Jenkins runs in its own compose project so redeploying the application never restarts it.

```bash
cd infra/jenkins
docker compose up -d --build
```

Then set it up once:

1. Get the initial admin password:
   ```bash
   docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
   ```
2. Open <http://localhost:8081> and enter the password on the **Unlock Jenkins** screen.
3. Choose **Install suggested plugins** (includes Git, GitHub, Pipeline, and Credentials Binding), then create the first admin account and confirm the Jenkins URL.
4. Go to **Manage Jenkins > Plugins > Available plugins** and install **Docker Pipeline**.
5. Verify Jenkins can reach the host's Docker engine:
   ```bash
   docker exec jenkins docker ps
   ```
6. Add the credentials under **Manage Jenkins > Credentials**:

   | Credential ID | Type | Used for |
   | --- | --- | --- |
   | `iskolaria-env` | Secret file | The production `.env` file. Copied into the workspace during Deploy and deleted afterwards. |
   | `discord-webhook` | Secret text | Discord webhook URL for build results. |

7. Create the pipeline job: **New Item > Pipeline**, then set **Definition** to *Pipeline script from SCM*, **SCM** to *Git*, enter the repository URL, set the branch to `main`, and set **Script Path** to `Jenkinsfile`. Save.
8. Run the job **once manually** (**Build Now**). Triggers declared in a Jenkinsfile only register after the first run. After that, every push starts a build.

### 3. Start the application stack

**Option A: through Jenkins (normal flow).** Push a commit to GitHub. Jenkins runs Checkout, Test, Build Images, Deploy, and Smoke Test, then reports the result to Discord.

**Option B: manually with Docker Compose.** From the repository root:

```bash
cp .env.example .env
# edit .env and replace every "change-me" value
docker compose up -d --build
```

Example `.env`:

```env
DB_NAME=scholarhub
DB_USER=scholar
DB_PASSWORD=change-me
JWT_SECRET=change-me-to-a-long-random-string
ADMIN_EMAIL=admin@scholarhub.test
ADMIN_PASSWORD=change-me-too
```

Open the application at <http://localhost:8080>. The footer shows the running build number.

**Seeded data (for testing)**

- Student numbers that can register: `202600123` (Juan Dela Cruz), `202600456` (Maria Santos), `202600789` (Jose Reyes)
- Admin account: created automatically at startup from `ADMIN_EMAIL` and `ADMIN_PASSWORD` in `.env`
- Scholarships: UAEB Scholarship and White Scholarship

**Useful commands**

```bash
docker compose ps                    # check container health
docker compose logs -f worker        # follow the worker logs
docker compose down                  # stop the stack (data is kept)
```

> Never run `docker compose down -v`. The `-v` flag deletes the named volumes and wipes the database and uploaded files.

**Rollback to an earlier build**

Run from the folder that contains the real `.env` (the pipeline deletes its own copy for security):

```bash
docker images | grep iskolaria                        # list available tags
TAG=15 docker compose -p iskolaria up -d --no-build   # redeploy build 15
```

---

## How the Trigger Is Configured

The pipeline starts automatically when new code is pushed to GitHub. Two triggers are declared in the `Jenkinsfile`:

```groovy
triggers {
    githubPush()                // fired by the GitHub webhook
    pollSCM('* * * * *')        // fallback: checks the repository every minute
}
```

- **Poll SCM (`* * * * *`)** is what the automatic deployment relies on. Jenkins checks the repository every minute and starts a build when it finds a new commit. This works even when Jenkins cannot be reached from the internet.
- **`githubPush()`** is the GitHub webhook trigger. A GitHub webhook cannot reach a Jenkins instance running on a local machine, which is why Poll SCM is used as the fallback. The webhook only works if Jenkins is publicly reachable.
- **First run is manual.** Triggers declared in a Jenkinsfile are registered only after the pipeline has run once, so the first build is started with **Build Now**. Every later build starts from a push.
- Other pipeline options: concurrent builds are disabled, the last 15 builds are kept, and each run has a 30-minute timeout.

---

## Team Members and Roles

**Group:** Team Ka Ba? | **Course/Section:** ITE302

| Member | Role | Responsibility |
| --- | --- | --- |
| Cabral, Bea Mei P. | Infrastructure Engineer | Architecture, Dockerfiles, `docker-compose.yml`, proxy |
| David, Nigel James L. | DevOps / CI-CD Engineer | Jenkins in Docker, credentials, triggers, Jenkinsfile |
| Serrano, Bianca Gabrielle R. | Project Lead / Scrum Master | Proposal, task board, Git repository management, demo flow |
| Serrano, Bianca Gabrielle R. | Backend and Database Engineer | API modules, DB schema and seed data, unit tests |
| Soriano, Den Mark C. | Frontend, QA, and Documentation Lead | Frontend, smoke test, README, documentation, slides |
