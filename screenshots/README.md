# Evidencia real de observabilidad

Corrida del **16/11/2026**, cinco solicitudes concurrentes con modelo real `claude-haiku-4-5-20251001`, API FastAPI, worker separado y Redis 8.

- [Ejecución exitosa en Actions](https://github.com/Agus1906/API-de-producci-n-y-monitoreo-activo/actions/runs/43929439155).
- Proyecto LangSmith: `preentrega7-entrega-validada` (sólo las cinco tareas de esta corrida).
- [Dashboard privado del workspace](https://smith.langchain.com/o/4c0b58ac-c0d3-4026-8f6e-459c2ea6d318/a/preentrega7-entrega-validada/dashboards/custom/a02655fb-66ea-4d06-979d-6bea73087b79).
- [JSON original de la prueba HTTP](load_test.json): cinco estados DONE e IDs para conciliación.

| Archivo | Evidencia |
|---|---|
| [01-traza-agentes.jpg](01-traza-agentes.jpg) | Supervisor, investigador, llamadas Anthropic y herramientas dentro del grafo real. |
| [02-costos-cinco-ejecuciones.jpg](02-costos-cinco-ejecuciones.jpg) | Cinco trazas exitosas, latencias, tokens y costo por ejecución calculado por LangSmith. |
| [03-latencia-p95.jpg](03-latencia-p95.jpg) | Dashboard con p95 **10,1 s** y cinco trazas. |
| [04-configuracion-p95.jpg](04-configuracion-p95.jpg) | Percentil **95** seleccionado, proyecto exacto, filtro `Is Trace=true` y cinco filas subyacentes. |
| [05-analista-tokens.jpg](05-analista-tokens.jpg) | Nodo analista, 1.372 tokens y herramienta `calculate_savings` sobre corpus simulado. |

Costos mostrados: USD 0,009728; 0,01003; 0,01024; 0,01639; 0,009538. Aproximadamente USD 0,0559 en total. Son costos calculados por la plataforma a partir de tokens y catálogo del modelo, no una factura del proveedor.

La tarea más lenta necesitó tres búsquedas. El supervisor concentró la latencia acumulada de esa traza; el analista tuvo el mayor consumo por llamada individual (1.372 tokens). El README amplía esta lectura.

La p95 del dashboard y la p95 del cliente son distintas: LangSmith aplica su agregación; el cliente mide hasta detectar DONE por polling y calcula nearest rank. Se conservan ambas sin sustituir una por otra. No se alteraron las capturas ni se simularon métricas. Las consultas y el corpus son ficticios y no contienen credenciales.
