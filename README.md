# Yap — Asistente IA local para ChincoLinux

**Yap** es un agente de inteligencia artificial local diseñado para entornos educativos con recursos limitados. Corre íntegramente en CPU, sin necesidad de conexión a Internet para su funcionamiento base. Está pensado para distribuciones Linux ligeras como **ChincoLinux** (basada en Debian estable).

## Objetivo del proyecto

Construir un sistema Debian estable ultraligero con un agente IA local (CPU-only) capaz de:

- Responder en **español** con enfoque educativo.
- Ejecutar **acciones seguras del sistema** mediante tooling controlado por whitelist.
- **Abrir aplicaciones** desde una lista blanca configurable.
- **Recuperar información** básica sobre aplicaciones o sitios web aprobados.
- Aplicar **restricciones y confirmaciones humanas** para acciones sensibles.
- Emitir **alertas gráficas** (notify-send) para mantener informado al usuario.

## Especificaciones técnicas

| Componente | Detalle |
|---|---|
| **Modelo** | Llama 3.2 3B Instruct (GGUF Q4_K_M) |
| **Runtime** | llama.cpp (CPU-only, sin GPU) |
| **RAM mínima** | 8 GB (4 GB útiles para el LLM + KV cache) |
| **Contexto** | 4k tokens por defecto |
| **Latencia** | ~2–3 s primeras tokens en CPU |
| **Idioma** | Español |
| **SO destino** | Debian estable (13, 64-bit) |

## Arquitectura

```
Usuario ──> CLI (yap) ──> Intérprete ──┬─> Whitelist de apps ──> Lanzar aplicación
                                        ├─> Whitelist web ──────> Webfetch
                                        └─> LLM local ──────────> Respuesta educativa

Alertas gráficas (notify-send) en cada acción.
```

### Componentes

- **`yap.py`** — Agente CLI que interpreta comandos del usuario y decide la acción.
- **`llama-cli`** — Runtime del modelo LLM local (CPU).
- **`whitelist/`** — Archivos de configuración con listas blancas de aplicaciones y dominios web.

## Instalación

### Requisitos

- Debian 13 (o derivada) 64-bit
- 8 GB RAM
- 5 GB de espacio libre en disco
- Conexión a Internet (solo durante la instalación)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/VECTORG99/Yap.git
cd Yap

# 2. Ejecutar el instalador
bash setup.sh
```

El script `setup.sh` realizará automáticamente:

1. Instalación de dependencias del sistema (build-essential, cmake, python3, etc.)
2. Compilación de `llama.cpp` desde fuente
3. Descarga del modelo Llama 3.2 3B Instruct (GGUF Q4_K_M, ~2 GB)
4. Instalación del agente Yap y sus listas blancas
5. Instalación de aplicaciones sugeridas (LibreOffice, Firefox, etc.)
6. Verificación de componentes

## Uso

### Modo interactivo

```bash
yap
Yap > Abre LibreOffice
```

### Modo comando directo

```bash
yap Abre LibreOffice
yap Busca https://es.wikipedia.org/wiki/Linux
yap ¿Qué es una partición de disco?
```

### Acciones soportadas

| Acción | Ejemplo | Descripción |
|---|---|---|
| Abrir app | `yap Abre LibreOffice` | Abre la app si está en whitelist |
| Webfetch | `yap Busca https://es.wikipedia.org/wiki/Linux` | Obtiene contenido del sitio si el dominio está en whitelist |
| Consulta LLM | `yap ¿Qué es Debian?` | Responde con el modelo LLM local |

## Seguridad

### Listas blancas

**Aplicaciones permitidas** (`/etc/yap/whitelist/apps.conf`):
- LibreOffice
- Evince (visor PDF)
- Firefox
- Micro (editor terminal)
- Htop (monitor del sistema)

**Dominios web permitidos** (`/etc/yap/whitelist/web.conf`):
- wikipedia.org
- debian.org

### Restricciones

- El agente **no ejecuta comandos arbitrarios** del sistema.
- Todas las acciones pasan por la whitelist correspondiente.
- Las acciones destructivas (borrar, instalar, cambiar permisos) están denegadas por defecto y requieren una capa adicional de confirmación humana (en desarrollo).
- Las alertas gráficas (`notify-send`) informan al usuario de cada acción ejecutada.

## Whitelist de aplicaciones (demo)

- LibreOffice
- Evince
- Firefox
- Micro
- Htop

## Limitaciones conocidas

- **Contexto limitado**: 4k tokens (~3000 palabras). Consultas muy largas pueden requerir resumen previo.
- **Sin conexión**: El modelo es 100% local, pero la bibliografía factual depende del webfetch desde la whitelist.
- **Calidad educativa**: El modelo Llama 3.2 3B Instruct puede alucinar información. Siempre que sea posible, se prefiere webfetch a fuentes verificadas.
- **Solo español**: El agente está optimizado para español; consultas en otros idiomas pueden dar resultados inconsistentes.

## Roadmap

### Fase 1 — MVP (actual)
- [x] LLM local (Llama 3.2 3B Instruct)
- [x] CLI interactiva y por comando directo
- [x] Tooling de sistema con whitelist
- [x] Alertas gráficas (notify-send)
- [x] Whitelist configurable de apps y dominios
- [x] Demo funcional (abrir app + info)

### Fase 2 — Próximos sprints
- [ ] Capa de confirmación humana para acciones sensibles
- [ ] Historial de contexto persistente
- [ ] Integración con AppArmor
- [ ] Instalador .deb
- [ ] Más fuentes en whitelist educativa
- [ ] Interfaz de configuración gráfica

### Fase 3 — Futuro
- [ ] Soporte multisesión
- [ ] Plugins de tooling extensibles
- [ ] Integración con gestores de cursos

## Demo (prueba mínima)

```bash
# Caso de prueba 1: Abrir app
yap Abre LibreOffice
# Resultado esperado: LibreOffice se abre + alerta + info de versión

# Caso de prueba 2: Webfetch
yap Busca https://es.wikipedia.org/wiki/Linux
# Resultado esperado: Contenido de la página

# Caso de prueba 3: Consulta
yap ¿Qué es Debian?
# Resultado esperado: Respuesta del LLM
```

## Licencia

Este proyecto se distribuye bajo licencia MIT. El modelo Llama 3.2 está sujeto a los términos de la [Licencia Llama 3.2](https://ai.meta.com/llama/license/).

## Contribuir

Las contribuciones son bienvenidas. Para cambios importantes, abre primero un issue para discutir qué te gustaría cambiar.
