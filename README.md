# Pre-entrega 7 â€” API de producciÃ³n y monitoreo activo

API **FastAPI asÃ­ncrona** que expone el orquestador del [MÃ³dulo 6](https://github.com/Agus1906/Orquestador-Multi-Agente-Especializado) mediante una cola durable en Redis. Conserva supervisor, investigador, analista, rÃºbrica de conciliaciÃ³n y corpus de pilotos **simulados**. El cÃ³digo de M6 se encapsula en `app/m6`; no requiere otros proyectos locales.

## Estado de la entrega

- Implementados: API, Redis Streams, checkpoints `AsyncRedisSaver`, worker separado, timeout/FAILED, HITL con aprobaciÃ³n autenticada, LangSmith y prueba de cinco solicitudes concurrentes.
- El modo `offline` ejecuta reglas y herramientas locales: **no llama a un LLM y no demuestra costos de inferencia**.
- **Pendiente de evidencia:** corrida con proveedor real y capturas del dashboard LangSmith de trazas, costo por ejecuciÃ³n y p95. No hay capturas ni mÃ©tricas inventadas. Ver `screenshots/README.md`.
- Es un prototipo acadÃ©mico con controles operativos; no supone una infraestructura productiva ya desplegada.

## 1. ConfiguraciÃ³n

Requiere Python **3.12+**, Docker Compose y Redis **8** (incluye JSON y Search, necesarios para el checkpointer; Redis bÃ¡sico antiguo no alcanza).

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

Swagger: [http://localhost:8000/docs](http://localhost:8000/docs). API y Redis se publican sÃ³lo en localhost. Para desarrollo sin contenedores de Python:

```powershell
docker compose up redis -d
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# En otra terminal, dentro de la misma carpeta:
.venv\Scripts\python.exe -m app.worker
```

API y worker cargan `.env` automÃ¡ticamente. La API no ejecuta inferencia: persiste estado y encola en una transacciÃ³n Redis antes de devolver **202**. Un worker apagado deja tareas pendientes.

## 2. Uso y aprobaciÃ³n humana

```powershell
$headers = @{ 'X-API-Key' = '<API_KEY configurada>' }
$body = @{query='Investiga pilotos RPA y calcula ahorro mensual'; action='analyze'} | ConvertTo-Json
$job = Invoke-RestMethod http://localhost:8000/tasks -Method Post -Headers $headers -ContentType application/json -Body $body
Invoke-RestMethod "http://localhost:8000/tasks/$($job.job_id)" -Headers $headers
```

`action=analyze` sÃ³lo calcula. `action=publish_report` se considera **siempre crÃ­tica**, independientemente del prompt: calcula, guarda el checkpoint y ejecuta `interrupt`. No publica hasta recibir aprobaciÃ³n externa. Publicar significa guardar el informe en Redis bajo `p7:report:<job_id>`; no envÃ­a correos ni modifica un sistema externo.

```powershell
$body = @{query='Investiga pilotos RPA y calcula ahorro mensual'; action='publish_report'} | ConvertTo-Json
$job = Invoke-RestMethod http://localhost:8000/tasks -Method Post -Headers $headers -ContentType application/json -Body $body
# Consultar GET /tasks/{job_id} hasta WAITING_APPROVAL y revisar result antes de aprobar.
$headers['X-Approval-Key'] = '<APPROVAL_KEY configurada>'
Invoke-RestMethod "http://localhost:8000/tasks/$($job.job_id)/approve" -Method Post -Headers $headers -ContentType application/json -Body '{"approved":true}'
```

Enviar `false` rechaza y finaliza en `REJECTED`, sin publicaciÃ³n. La aprobaciÃ³n usa compare-and-set atÃ³mico; repetirla devuelve 409. UUID inexistente: 404; cuerpo invÃ¡lido: 422; clave ausente/incorrecta: 401/403; Redis indisponible: 503.

Estados: `PENDING â†’ RUNNING â†’ DONE | FAILED | WAITING_APPROVAL`; desde aprobaciÃ³n: `PENDING â†’ RUNNING â†’ DONE | REJECTED`.

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

El script envÃ­a **cinco POST concurrentes**, consulta los estados y guarda IDs/tiempos en `output/load_test.json`. Falla si alguna tarea no termina en DONE. `client_p95_seconds` usa nearest rank (con cinco observaciones corresponde al mÃ¡ximo); incluye cola y polling y **no sustituye la p95 del dashboard**.

LangGraph/LangChain propagan callbacks a cada nodo y llamada `ChatOpenAI`. `task_execution` agrega una traza raÃ­z por trabajo; `metadata.job_id` permite buscar exactamente los cinco IDs. LangSmith recibe modelo, proveedor y uso real de tokens del cliente para calcular costos segÃºn su catÃ¡logo; no se estiman precios en el cÃ³digo. Verificar que el modelo tenga precio en LangSmith.

En el proyecto LangSmith, filtrar por esos IDs y el intervalo de la corrida, abrir las trazas de los nodos, visualizar **Total Cost por ejecuciÃ³n** y el panel **p95 de latencia**. Guardar capturas en `screenshots/`. Revisar quÃ© nodo concentra latencia y tokens. No mezclar spans hijos o ejecuciones anteriores con las cinco trazas raÃ­z. Cinco muestras sirven como demostraciÃ³n, no como benchmark representativo.

Las trazas pueden contener consultas y corpus. Usar sÃ³lo datos autorizados; nunca claves en prompts, logs o capturas. Si LangSmith no entrega trazas, revisar la configuraciÃ³n y el dashboard: Ã©xito del job no garantiza entrega de telemetrÃ­a.

## 4. RecuperaciÃ³n, lÃ­mites y operaciÃ³n

Redis Streams conserva mensajes hasta el ACK. Los consumidores recuperan pendientes abandonados mediante `XAUTOCLAIM` despuÃ©s de `JOB_TIMEOUT + 60` segundos. Un lock por job evita dos ejecuciones simultÃ¡neas; su lease supera el timeout. Los checkpoints usan `thread_id=job_id`: al recuperar un RUNNING se continÃºa desde el estado guardado. La aprobaciÃ³n conserva el mismo thread.

Una excepciÃ³n o timeout actualiza FAILED con el **tipo de error**, sin publicar mensajes remotos o secretos. No se reintenta automÃ¡ticamente un FAILED; crear otra tarea es una acciÃ³n explÃ­cita. La cola ofrece entrega al menos una vez; la publicaciÃ³n local es idempotente por clave de job. Antes de integrar efectos externos reales se requiere una clave de idempotencia transaccional del sistema destino. Dos POST independientes generan dos trabajos: no hay deduplicaciÃ³n entre solicitudes.

Si Redis cae, no se reconoce el mensaje y el supervisor del contenedor reinicia el worker; se recupera cuando vuelve Redis. AOF y volumen persisten reinicios, pero `appendfsync everysec` admite pÃ©rdida aproximada del Ãºltimo segundo ante una caÃ­da brusca. La computadora apagada **no procesa tareas**; para servicio continuo desplegar en un servidor encendido. No ejecutar `docker compose down -v` si se necesita conservar estado.

Pendientes para un entorno empresarial: TLS/reverse proxy, identidad individual y roles, rotaciÃ³n de secretos, lÃ­mites de solicitudes, backups, alertas externas y polÃ­ticas de retenciÃ³n. En este prototipo los jobs, informes y checkpoints no vencen; planificar limpieza y capacidad de Redis. Los fallos se ven por polling y logs; no se ha configurado un canal externo de notificaciones.

## 5. ValidaciÃ³n

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pip check
# Redis real: usar una INSTANCIA de pruebas separada (Search requiere db 0).
$env:TEST_REDIS_URL = 'redis://localhost:6379/0'
.venv\Scripts\python.exe -m pytest tests/test_redis_integration.py -q
```

Pruebas: regresiÃ³n M6, validaciones y conciliaciÃ³n, cinco ingresos concurrentes, autenticaciÃ³n, HITL, aprobaciÃ³n Ãºnica, rechazo, FAILED y timeout. Las pruebas unitarias usan FakeRedis e InMemorySaver; las pruebas integradas verifican Redis real y reapertura del checkpointer y se omiten sin `TEST_REDIS_URL`. GitHub Actions levanta Redis 8 y las ejecuta.

## Estructura

`app/main.py`: endpoints; `store.py`: estado/cola; `worker.py`: consumo y recuperaciÃ³n; `graph.py`: orquestador y checkpoints; `hitl.py`: interrupciÃ³n; `observability.py`: proveedor y tracing; `m6/`: agentes/herramientas/corpus originales encapsulados; `scripts/load_test.py`: carga; `tests/`: verificaciones.

Fuentes tÃ©cnicas: [Redis AsyncRedisSaver](https://redis-developer.github.io/langgraph-redis/main/api/async_checkpoint_saver.html), [tracing LangSmith](https://docs.langchain.com/langsmith/trace-with-langchain), [costos LangSmith](https://docs.langchain.com/langsmith/cost-tracking).
