# Política de seguridad

## Reportar una vulnerabilidad

No abras un issue público. Usa **Security → Report a vulnerability** en GitHub
(reporte privado) e incluye los pasos para reproducirla.

## Controles de este repositorio

| Riesgo | Control |
| --- | --- |
| Dependencias con CVEs | pip-audit en cada PR y Dependabot semanal |
| Vulnerabilidades en el código | CodeQL y reglas de seguridad de Ruff (bandit) |
| Calidad y Quality Gate | SonarCloud |
| Secretos en el código o el historial | Gitleaks en el pipeline y como pre-commit |
| Imagen con vulnerabilidades | Trivy bloquea HIGH y CRITICAL |
| Configuración insegura de Docker o Kubernetes | Trivy config |
| Contenedor con demasiados permisos | Usuario sin root, sistema de archivos de solo lectura, sin capabilities |
| Permisos excesivos del pipeline | `permissions: contents: read` por defecto |
