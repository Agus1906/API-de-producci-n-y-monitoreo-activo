# Pre-entrega 7 — API de producción y monitoreo activo

API **FastAPI asíncrona** que expone el orquestador del [Módulo 6](https://github.com/Agus1906/Orquestador-Multi-Agente-Especializado) mediante una cola durable en Redis. Conserva supervisor, investigador, analista, rúbrica de conciliación y corpus de pilotos **simulados**. El código de M6 se encapsula en `app/m6`; no requiere otros proyectos locales.

## Estado de la entrega

- Implementados: API, Redis Streams, checkpoints `AsyncRedisSaver`, worker separado, timeout/FAILED, HITL con aprobación autenticada, LangSmith y prueba de cinco solicitudes concurrentes.
- El modo `offline` ejecuta reglas y herramientas locales: **no llama a un LLM y no demuestra costos de inferencia**.
- **Pendiente de evidencia:** corrida con proveedor real y capturas del dashboard LangSmith de trazas, costo por ejecución y p95. No hay capturas ni métricas inventadas. Ver `screenshots/README.md`.
- Es un prototipo académico con controles operativos; no supone una infraestructura productiva ya desplegada.

**Validación con Redis real:** [GitHub Actions](https://github.com/Agus1906/API-de-producci-n-y-monitoreo-activo/actions/runs/43926777844) ejecutó satisfactoriamente 29 pruebas y cinco solicitudes concurrentes por HTTP con API y worker separados, todas en DONE. En esa corrida offline, el tiempo de encolado fue de 24–42 ms y la p95 del cliente fue 1,053 s (incluye polling de un segundo). El JSON se conserva como artefacto `offline-load-test` de Actions. Estas mediciones no son costos ni p95 de LangSmith.

## 1. Configuración

Requiere Python **3.12+**, Docker Compose y Redis **8** (incluye JSON y Search, necesarios para el checkpointer; Redis básico antiguo no alcanza).

```powershell
git clone https://github.com/Agus1906/API-de-producci-n-y-monitoreo-activo.git
cd API-de-producci-n-y-monitoreo-activo
Copy-Item .env.example .env
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Editar `.env`: asignar claves largas y **diferentes** a `API_KEY` y `APPROVAL_KEY`. Para reproducir las versiones verificadas usar `requirements-lock.txt` en lugar de `requirements-dev.txt` (incluye herramientas de prueba).

```powershell
docker compose up --build -d
Invoke-RestMethod http://localhost:8000/health
```

Swagger: [http://localhost:8000/docs](http://localhost:8000/docs). API y Redis se publican sólo en localhost. Para desarrollo sin contenedores de Python:

```powershell
docker compose up redis -d
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# En otra terminal, dentro de la misma carpeta:
.venv\Scripts\python.exe -m app.worker
```

API y worker cargan `.env` automáticamente. La API no ejecuta inferencia: persiste estado y encola en una transacción Redis antes de devolver **202**. Un worker apagado deja tareas pendientes.

## 2. Uso y aprobación humana

```powershell
$headers = @{ 'X-API-Key' = '<API_KEY configurada>' }
$body = @{query='Investiga pilotos RPA y calcula ahorro mensual'; action='analyze'} | ConvertTo-Json
$job = Invoke-RestMethod http://localhost:8000/tasks -Method Post -Headers $headers -ContentType application/json -Body $body
Invoke-RestMethod "http://localhost:8000/tasks/$($job.job_id)" -Headers $headers
```

`action=analyze` sólo calcula. `action=publish_report` se considera **siempre crítica**, independientemente del prompt: calcula, guarda el checkpoint y ejecuta `interrupt`. No publica hasta recibir aprobación externa. Publicar significa guardar el informe en Redis bajo `p7:report:<job_id>`; no envía correos ni modifica un sistema externo.

```powershell
$body = @{query='Investiga pilotos RPA y calcula ahorro mensual'; action='publish_report'} | ConvertTo-Json
$job = Invoke-RestMethod http://localhost:8000/tasks -Method Post -Headers $headers -ContentType application/json -Body $body
# Consultar GET /tasks/{job_id} hasta WAITING_APPROVAL y revisar result antes de aprobar.
$headers['X-Approval-Key'] = '<APPROVAL_KEY configurada>'
Invoke-RestMethod "http://localhost:8000/tasks/$($job.job_id)/approve" -Method Post -Headers $headers -ContentType application/json -Body '{"approved":true}'
```

Enviar `false` rechaza y finaliza en `REJECTED`, sin publicación. La aprobación usa compare-and-set atómico; repetirla devuelve 409. UUID inexistente: 404; cuerpo inválido: 422; clave ausente/incorrecta: 401/403; Redis indisponible: 503.

Estados: `PENDING → RUNNING → DONE | FAILED | WAITING_APPROVAL`; desde aprobación: `PENDING → RUNNING → DONE | REJECTED`.

## 3. Observabilidad activa y cinco peticiones

Configurar en `.env` y recrear el worker:

```dotenv
AGENT_MODE=llm
OPENAI_API_KEY=<clave local>
OPENAI_MODEL=gpt-4.1-mini
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=<clave local>
LANGSMITH_PROJECT=preentrega7
```

```powershell
docker compose up -d --force-recreate worker
.venv\Scripts\python.exe scripts/load_test.py
```

El script envía **cinco POST concurrentes**, consulta los estados y guarda IDs/tiempos en `output/load_test.json`. Falla si alguna tarea no termina en DONE. `client_p95_seconds` usa nearest rank (con cinco observaciones corresponde al máximo); incluye cola y polling y **no sustituye la p95 del dashboard**.

LangGraph/LangChain propagan callbacks a cada nodo y llamada `ChatOpenAI`. `task_execution` agrega una traza raíz por trabajo; `metadata.job_id` permite buscar exactamente los cinco IDs. LangSmith recibe modelo, proveedor y uso real de tokens del cliente para calcular costos según su catálogo; no se estiman precios en el código. Verificar que el modelo tenga precio en LangSmith.

En el proyecto LangSmith, filtrar por esos IDs y el intervalo de la corrida, abrir las trazas de los nodos, visualizar **Total Cost por ejecución** y el panel **p95 de latencia**. Guardar capturas en `screenshots/`. Revisar qué nodo concentra latencia y tokens. No mezclar spans hijos o ejecuciones anteriores con las cinco trazas raíz. Cinco muestras sirven como demostración, no como benchmark representativo.

Las trazas pueden contener consultas y corpus. Usar sólo datos autorizados; nunca claves en prompts, logs o capturas. Si LangSmith no entrega trazas, revisar la configuración y el dashboard: éxito del job no garantiza entrega de telemetría.

## 4. Recuperación, límites y operación

Redis Streams conserva mensajes hasta el ACK. Los consumidores recuperan pendientes abandonados mediante `XAUTOCLAIM` después de `JOB_TIMEOUT + 60` segundos. Un lock por job evita dos ejecuciones simultáneas; su lease supera el timeout. Los checkpoints usan `thread_id=job_id`: al recuperar un RUNNING se continúa desde el estado guardado. La aprobación conserva el mismo thread.

Una excepción o timeout actualiza FAILED con el **tipo de error**, sin publicar mensajes remotos o secretos. No se reintenta automáticamente un FAILED; crear otra tarea es una acción explícita. La cola ofrece entrega al menos una vez; la publicación local es idempotente por clave de job. Antes de integrar efectos externos reales se requiere una clave de idempotencia transaccional del sistema destino. Dos POST independientes generan dos trabajos: no hay deduplicación entre solicitudes.

Si Redis cae, no se reconoce el mensaje y el supervisor del contenedor reinicia el worker; se recupera cuando vuelve Redis. AOF y volumen persisten reinicios, pero `appendfsync everysec` admite pérdida aproximada del último segundo ante una caída brusca. La computadora apagada **no procesa tareas**; para servicio continuo desplegar en un servidor encendido. No ejecutar `docker compose down -v` si se necesita conservar estado.

Pendientes para un entorno empresarial: TLS/reverse proxy, identidad individual y roles, rotación de secretos, límites de solicitudes, backups, alertas externas y políticas de retención. En este prototipo los jobs, informes y checkpoints no vencen; planificar limpieza y capacidad de Redis. Los fallos se ven por polling y logs; no se ha configurado un canal externo de notificaciones.

## 5. Validación

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pip check
# Redis real: usar una INSTANCIA de pruebas separada (Search requiere db 0).
$env:TEST_REDIS_URL = 'redis://localhost:6379/0'
.venv\Scripts\python.exe -m pytest tests/test_redis_integration.py -q
```

Pruebas: regresión M6, validaciones y conciliación, cinco ingresos concurrentes, autenticación, HITL, aprobación única, rechazo, FAILED y timeout. Las pruebas unitarias usan FakeRedis e InMemorySaver; las pruebas integradas verifican Redis real y reapertura del checkpointer y se omiten sin `TEST_REDIS_URL`. GitHub Actions levanta Redis 8 y las ejecuta.

## Estructura

`app/main.py`: endpoints; `store.py`: estado/cola; `worker.py`: consumo y recuperación; `graph.py`: orquestador y checkpoints; `hitl.py`: interrupción; `observability.py`: proveedor y tracing; `m6/`: agentes/herramientas/corpus originales encapsulados; `scripts/load_test.py`: carga; `tests/`: verificaciones.

Fuentes técnicas: [Redis AsyncRedisSaver](https://redis-developer.github.io/langgraph-redis/main/api/async_checkpoint_saver.html), [tracing LangSmith](https://docs.langchain.com/langsmith/trace-with-langchain), [costos LangSmith](https://docs.langchain.com/langsmith/cost-tracking).
