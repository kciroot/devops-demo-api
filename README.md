# DevOps demo: Tasks API

Una API REST de tareas con base de datos y un flujo DevOps completo: pruebas,
calidad, seguridad, contenedores, despliegue en Kubernetes y monitoreo. Todas
las herramientas son gratuitas para repositorios públicos.

```
Desarrollador ── PR ──► GitHub Actions
                         ├─ 1. Lint (Ruff) + pruebas (pytest) + cobertura
                         │     └─ SonarCloud + Quality Gate
                         ├─ 2. pip-audit (CVEs) + Gitleaks (secretos)
                         ├─ CodeQL (SAST, workflow aparte)
                         ├─ 3. Build de la imagen Docker (una sola vez)
                         │     ├─ Trivy: imagen (bloquea HIGH/CRITICAL)
                         │     ├─ Trivy: Dockerfile y manifiestos K8s
                         │     ├─ Deploy a un clúster kind (Kubernetes)
                         │     └─ Smoke test contra la API desplegada
                         └─ 4. Solo en main: publicar la MISMA imagen en GHCR
                                                   │
                                Prometheus ◄── /metrics ── API ──► logs JSON
                                     │
                                  Grafana (panel) + alertas
```

## La aplicación

| Endpoint | Qué hace |
| --- | --- |
| `GET /health` | Liveness: el proceso está vivo |
| `GET /ready` | Readiness: la base de datos responde |
| `GET /metrics` | Métricas en formato Prometheus |
| `GET /api/v1/tasks?done=true&limit=10&offset=0` | Lista tareas con filtro y paginación |
| `POST /api/v1/tasks` | Crea una tarea (`title` obligatorio) |
| `GET /api/v1/tasks/{id}` | Obtiene una tarea |
| `PUT` o `PATCH /api/v1/tasks/{id}` | Actualiza `title`, `description` o `done` |
| `DELETE /api/v1/tasks/{id}` | Borra una tarea |

**Stack:** Python 3.13, Flask, SQLite y Gunicorn. Solo 3 dependencias de ejecución,
fijadas a versiones exactas, para reducir la superficie de ataque.

**Medidas de seguridad en el código:** consultas parametrizadas (contra SQL
injection), validación estricta del JSON, límite de 16 KB por petición, campos
desconocidos rechazados y cabeceras de seguridad en cada respuesta.

## Cómo se comporta

### La API

```bash
$ curl -X POST localhost:8000/api/v1/tasks -H 'Content-Type: application/json' \
       -d '{"title":"Preparar entrevista DevOps"}'
{"created_at":"2026-10-28T21:36:15+00:00","description":"","done":false,"id":2,
 "title":"Preparar entrevista DevOps","updated_at":"2026-10-28T21:36:15+00:00"}   # 201

$ curl -X POST localhost:8000/api/v1/tasks -H 'Content-Type: application/json' -d '{"titulo":"x"}'
{"error":"unknown fields: titulo"}                                                 # 400

$ curl localhost:8000/ready
{"database":"up","status":"ready"}                                                 # 200
```

Cada petición deja un log en JSON, listo para ELK, Loki o Splunk:

```json
{"ts": "2026-10-28T21:36:15", "level": "INFO", "logger": "tasks_api", "msg": "request",
 "method": "POST", "path": "/api/v1/tasks", "status": 201, "duration_ms": 2.64}
```

### El pipeline ante cada situación

| Situación | Qué pasa |
| --- | --- |
| Abres un pull request | Corren lint, pruebas, SonarCloud, pip-audit, Gitleaks, CodeQL, build, Trivy, deploy a kind y smoke test |
| Falla una prueba o la cobertura baja de 80 % | El job `test` falla y no se construye la imagen |
| SonarCloud no aprueba el Quality Gate | El job falla (`sonar.qualitygate.wait=true`) |
| Una dependencia tiene un CVE conocido | pip-audit falla y bloquea el PR |
| Alguien sube una contraseña o un token | Gitleaks lo detecta, incluso en el historial |
| La imagen tiene una vulnerabilidad HIGH o CRITICAL con parche | Trivy falla y la imagen no avanza |
| El Dockerfile o los YAML de Kubernetes son inseguros | Trivy config falla |
| El pod no arranca o no pasa los probes | `rollout status` falla y se imprimen los logs del pod |
| Todo pasa en `main` | Se publica en GHCR la misma imagen probada, con tag del commit |
| Sale una versión nueva de una dependencia o de una acción | Dependabot abre un PR y el pipeline lo prueba |

### En ejecución

- **Kubernetes:** si `/health` falla, Kubernetes reinicia el contenedor. Si `/ready`
  falla, deja de enviarle tráfico sin reiniciarlo.
- **Prometheus** recolecta `/metrics` cada 15 s. Las alertas definidas son: API
  caída (1 min), más de 5 % de errores 5xx (5 min) y latencia p95 sobre 500 ms (5 min).
- **Grafana** muestra un panel con estado, total de tareas, peticiones por estado
  HTTP y latencia p95 por ruta.

## Ejecutarlo en local

```bash
make install     # crea .venv e instala dependencias
make check       # lint + pruebas + auditoría de dependencias
make run         # API en http://127.0.0.1:8000
make smoke       # en otra terminal: prueba la API de punta a punta
```

Con Docker, incluido el monitoreo:

```bash
cp .env.example .env          # cambia la contraseña de Grafana
make up                       # API :8000 · Prometheus :9090 · Grafana :3000
make smoke
make down
```

En un Kubernetes local con [kind](https://kind.sigs.k8s.io/):

```bash
make kind-deploy
kubectl -n tasks-api port-forward service/tasks-api 8080:80
bash scripts/smoke_test.sh http://localhost:8080
```

## Publicarlo en GitHub

1. Crea un repositorio **público** vacío en GitHub (por ejemplo `devops-demo-api`).
2. Sube el código:
   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit: DevOps demo"
   git remote add origin https://github.com/TU_USUARIO/devops-demo-api.git
   git push -u origin main
   ```
3. El pipeline corre solo. Míralo en la pestaña **Actions**.
4. **SonarCloud (opcional, gratis):** entra a sonarcloud.io con GitHub, importa el
   repositorio y elige *GitHub Actions* como método de análisis. Copia tu
   organización y la clave del proyecto en `sonar-project.properties`, y guarda el
   token como secreto `SONAR_TOKEN` en *Settings → Secrets and variables → Actions*.
   Desactiva el *Automatic Analysis* de SonarCloud para que no choque con el del
   pipeline. Sin el secreto, ese paso simplemente se salta.
5. **Aprobación manual antes de publicar:** en *Settings → Environments* crea
   `production` y agrega revisores requeridos.
6. **Proteger main:** en *Settings → Branches* exige pull request y que pasen los
   checks antes del merge.

## Estructura

```
app/            API: rutas, acceso a datos y métricas
tests/          19 pruebas: CRUD, validación, salud, métricas y seguridad
k8s/            Namespace restringido, PVC, Deployment, Service (Kustomize)
monitoring/     Prometheus, alertas y Grafana provisionado
scripts/        Smoke test usado por el pipeline y en local
.github/        Pipeline CI/CD, CodeQL, Dependabot y plantilla de PR
Dockerfile      Multi-stage, usuario sin root, healthcheck
```

## Decisiones y límites (para explicarlo en una entrevista)

- **Construir una vez, desplegar muchas.** El pipeline guarda la imagen probada
  y publica exactamente esa, no una reconstruida.
- **Tags por commit.** Cada imagen lleva el SHA corto del commit, así el rollback
  es volver a un tag anterior. `latest` se publica solo como conveniencia.
- **SQLite con una réplica.** Es suficiente para la demo. Para escalar
  horizontalmente habría que pasar a PostgreSQL, quitar el volumen
  `ReadWriteOnce` y agregar un HPA. Por la misma razón el despliegue usa la
  estrategia `Recreate` en lugar de `RollingUpdate`.
- **Seguridad de la cadena de suministro.** Las acciones de terceros se fijan
  por versión. Para producción, fíjalas por commit SHA: en marzo de 2026 varias
  etiquetas de `trivy-action` fueron comprometidas (CVE-2026-33634), y por eso
  este pipeline usa `trivy-action` 0.35.0 con Trivy v0.69.3.
- **Mínimo privilegio en todas partes:** el pipeline solo tiene `contents: read`
  salvo el job que publica; el contenedor corre sin root, con sistema de
  archivos de solo lectura y sin capabilities.

## Qué se verificó

En el entorno donde se generó este repositorio se ejecutaron las 19 pruebas
(todas pasan) y el smoke test contra la API corriendo. Ese entorno no tenía
acceso a PyPI, Docker Hub ni GitHub, así que estas partes se validan en tu
primer push: la construcción de la imagen, los escaneos de Ruff, pip-audit,
Trivy, Gitleaks y CodeQL, y el despliegue en kind. Si algún escaneo encuentra
algo, el pipeline te dice exactamente qué y dónde.
