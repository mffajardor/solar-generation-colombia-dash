# 🇨🇴 Análisis de Generación Eléctrica — Colombia (API XM)

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?logo=pandas)](https://pandas.pydata.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-v1%20ETL%20%2B%20EDA-blue)]()

> Pipeline ETL reproducible + análisis exploratorio del mercado eléctrico colombiano usando la API pública de XM.

---

## 📋 Tabla de Contenidos

- [Descripción del Proyecto](#-descripción-del-proyecto)
- [Contexto: El Mercado Eléctrico Colombiano y XM](#-contexto-el-mercado-eléctrico-colombiano-y-xm)
- [La API de XM y pydataxm](#-la-api-de-xm-y-pydataxm)
- [Arquitectura del Pipeline ETL](#-arquitectura-del-pipeline-etl)
- [Estructura del Repositorio](#-estructura-del-repositorio)
- [Instalación y Uso](#-instalación-y-uso)
			  
- [Análisis Exploratorio — Hallazgos Clave](#-análisis-exploratorio--hallazgos-clave)
- [Catálogo de Métricas XM](#-catálogo-de-métricas-xm)
- [Roadmap del Proyecto](#-roadmap-del-proyecto)
- [Stack Tecnológico](#-stack-tecnológico)
- [Autor](#-autor)
- [Licencia](#-licencia)


---

## 🎯 Descripción del Proyecto

Este proyecto construye un **pipeline ETL (Extract–Transform–Load) reproducible** que extrae datos de generación eléctrica en tiempo real desde la API pública de XM — el operador del mercado eléctrico de Colombia — los transforma en un **modelo dimensional limpio** (star schema), y entrega un análisis exploratorio del parque generador del Sistema Interconectado Nacional (SIN).

### Preguntas que responde

1. **¿Cómo se distribuye la generación por tecnología?** — Participación porcentual de Solar, Hidráulica, Térmica, Eólica y Cogeneración en la generación total del SIN.
2. **¿Cuál es el perfil horario típico de generación solar en Colombia?** — Curva de campana H01–H24 y complementariedad con la generación hidráulica.
3. **¿Qué tan concentrado está el mercado por agente generador?** — Top 15 agentes, participación por tecnología.
4. **¿Cuál es la composición real del parque solar?** — Desglose por tipo de recurso: Autogeneración de Pequeña Escala, Generación Distribuida, Autogeneradores y plantas despachadas centralmente.

### ¿Por qué es relevante?

Colombia está en plena transición energética. La regulación CREG 174-2021 impulsó la autogeneración de pequeña escala, y el país pasó de ~30 recursos solares en 2020 a más de 800 en 2025, aunque la mayoría aporta individualmente poca energía. Este proyecto permite analizar cuantitativamente esa transformación usando datos oficiales.

---

## 🏛️ Contexto: El Mercado Eléctrico Colombiano y XM

### ¿Qué es XM?

**XM S.A. E.S.P.** es la empresa que opera el **Sistema Interconectado Nacional (SIN)** y administra el **Mercado de Energía Mayorista (MEM)** de Colombia. Sus funciones principales:

- **Centro Nacional de Despacho (CND):** Programa y coordina la operación del sistema eléctrico en tiempo real.
- **Administrador del Sistema de Intercambios Comerciales (ASIC):** Liquida las transacciones de energía entre agentes.
- **Administrador de Cuentas de Liquidación (LAC):** Gestiona la cadena de pagos del mercado.

### El Sistema Interconectado Nacional (SIN)

El SIN conecta la generación, transmisión, distribución y comercialización de electricidad en Colombia. La capacidad instalada (~18.8 GW) se distribuye así:

| Tecnología | Participación aprox. | Rol en el sistema |
|:-----------|:---------------------|:------------------|
| 🌊 **Hidráulica** | ~65% de la energía | Base del sistema. Sensible a El Niño (aportes hídricos) |
| 🔥 **Térmica** | ~28% de la energía | Respaldo. Gas natural, carbón, fuel oil. Define precio de bolsa en horas pico |
| ☀️ **Solar** | ~3% energía, ~84% en número de recursos | Crecimiento explosivo en GD y autogeneración. Perfil de campana (pico 10am–3pm) |
| 💨 **Eólica** | <1% (en expansión) | Proyectos en La Guajira, fase de construcción y puesta en marcha |
| ⚙️ **Cogeneración** | ~3% | Industria azucarera (bagazo), sector industrial |

### Métricas clave del mercado

- **`Gene` (Generación Real):** Energía producida por cada recurso, reportada en kWh por hora (H1–H24) por día.
- **`DemaReal` (Demanda Real):** Consumo de usuarios regulados y no regulados del SIN.
- **`PrecBolsNaci` (Precio de Bolsa Nacional):** Precio spot horario del mercado mayorista, en COP/kWh.
- **`PorcVoluUtilDiar` (Nivel de Embalses):** Porcentaje de capacidad útil de los embalses, indicador clave de seguridad energética.

---

## 📡 La API de XM y `pydataxm`

### API Pública de XM

XM expone una **API REST pública** que permite consultar datos operativos y comerciales del SIN. No requiere autenticación (API key), pero tiene restricciones:

- **Límite por consulta:** Máximo **31 días** por llamada para métricas horarias.
- **Niveles de agregación (Entity):** `Sistema`, `Agente`, `Recurso`, `Rio`, `Embalse`, `Area`, `SubArea`, entre otros.
- **Formato de respuesta:** JSON con estructura `{Id, Values_code, Values_Hour01...Values_Hour24, Date}`.
- **Catálogo de métricas:** **190 métricas** (139 únicas) agrupadas en categorías como generación, demanda, precios, emisiones, aportes hídricos y capacidad instalada.

### La librería `pydataxm`

[`pydataxm`](https://github.com/EquipoAnwor662015/pydataxm) es un wrapper de Python que simplifica el acceso a la API de XM:

```python
from pydataxm import pydataxm
import datetime as dt

api = pydataxm.ReadDB()

# Descargar generación real por recurso (últimos 7 días)
df = api.request_data(
    "Gene",                               # MetricId
    "Recurso",                             # Entity level
    dt.date(2025, 6, 1),                   # fecha_inicio
    dt.date(2025, 6, 7)                    # fecha_fin (máx. 31 días)
)
```

**Características clave:**
- Descarga directa de cualquier métrica por nivel de agregación.
- Retorna `pandas.DataFrame` listo para análisis.
- Sin autenticación, sin API keys, sin límite de llamadas diarias (pero sí de días por consulta).

### Modos de operación del notebook

El notebook soporta **3 modos** para flexibilidad total:

| Modo | Descripción | Requiere API |
|:-----|:------------|:-------------|
| `API` | Descarga automáticamente los últimos 30 días (D-1) | ✅ |
| `FIJO` | Descarga un rango de fechas específico (para estudios históricos: El Niño, racionamientos, etc.) | ✅ |
| `CSV` | Carga datos previamente descargados desde `data/raw/` | ❌ |

Esto permite que cualquier persona reproduzca el análisis sin acceso a internet, usando los CSVs incluidos en el repositorio.

---
## 🔧 Arquitectura del Pipeline ETL

```
┌────────────────────┐      melt()       ┌───────────────────┐      merge()      ┌─────────────────────────┐
│  datos_crudos       │  ──────────────►  │  fact_generacion  │  ──────────────►  │  generacion_enriquecida │
│  (wide: 24 cols/h)  │                   │  (long: 1 fila/h) │                   │  (+ metadatos planta)   │
└────────────────────┘                    └───────────────────┘                   └─────────────────────────┘
                                                                       ▲
                                                              ┌────────┴────────┐
                                                              │   dim_plantas   │
                                                              │   dim_agentes   │
                                                              │   dim_rios      │
                                                              └─────────────────┘
```

### Modelo Dimensional (Star Schema)

- **Tabla de hechos (`fact_generacion`):** Una fila por planta × hora × día. Columnas: `Fecha`, `Hora`, `Codigo_Planta`, `Generacion_kWh`.
- **Dimensión plantas (`dim_plantas`):** Código, nombre, tecnología, fuente de energía, tipo de recurso (RecType), tipo de despacho, agente propietario.
- **Dimensión agentes (`dim_agentes`):** Empresas participantes del MEM.
- **Dimensión ríos (`dim_rios`):** Cuencas hidrográficas asociadas a plantas hidráulicas.

### Auto-refresh de Catálogos

El parque generador crece constantemente. Si el ETL detecta plantas en los datos de generación que no existen en el catálogo maestro, automáticamente descarga catálogos frescos desde la API, re-ejecuta el JOIN, y reporta las plantas que aún no tienen match.

---

## 📂 Estructura del Repositorio

```
solar-generation-colombia/
│
├── notebooks/
│   └── 01_ETL_exploracion_v1.ipynb       # Pipeline ETL + EDA completo
│
├── src/
│   ├── extraccion.py                      # Funciones de descarga desde la API XM
│   ├── etl.py                             # Pipeline de transformación (wide → long)
│   └── visualizaciones.py                 # Funciones de gráficos reutilizables
│
├── data/
│   ├── raw/                               # Datos crudos con estampa YYYYMMDD
│   │   ├── datos_generacion_YYYYMMDD.csv  # Generación real (Gene) por recurso
│   │   ├── dim_plantas_YYYYMMDD.csv       # Catálogo de recursos generadores
│   │   ├── dim_agentes_YYYYMMDD.csv       # Catálogo de agentes del mercado
│   │   └── dim_rios_YYYYMMDD.csv          # Catálogo de cuencas hidrográficas
│   └── processed/                         # Outputs limpios del ETL
│       ├── fact_generacion_YYYYMMDD.csv
│       ├── generacion_enriquecida_YYYYMMDD.csv
│       └── dim_plantas_clean_YYYYMMDD.csv
│
├── app/                                    # Dashboard Streamlit (v4 — futuro)
│
├── .gitignore
├── README.md
└── requirements.txt
```

---

## ⚙️ Instalación y Configuración

### Requisitos previos

- Python 3.10+
- pip

### Instalación rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/xm-energia-colombia.git
cd xm-energia-colombia

# 2. Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

### `requirements.txt`

```
pydataxm>=0.3.0
pandas>=2.0
matplotlib>=3.7
seaborn>=0.12
```

### Ejecución sin API (modo CSV)

Si no tienes acceso a internet o no deseas instalar `pydataxm`, el notebook detecta automáticamente si la librería está disponible y usa los CSVs incluidos en `data/raw/`:

```python
# El notebook maneja esto automáticamente:
try:
    from pydataxm import pydataxm
    API_DISPONIBLE = True
except ImportError:
    API_DISPONIBLE = False
    # → Usa los archivos CSV de data/raw/
```

---

## 🚀 Uso

### Opción 1: Modo interactivo (Jupyter)

```bash
jupyter notebook notebooks/01_ETL_exploracion_v1.ipynb
```

Selecciona el modo de operación en la celda de configuración:

```python
MODO = "API"   # Descarga últimos 30 días en vivo
MODO = "FIJO"  # Rango de fechas personalizado (ej: evento El Niño)
MODO = "CSV"   # Usa datos locales (sin internet)
```

### Opción 2: Reproducir con datos incluidos

Sin modificar nada, el notebook carga los CSVs de muestra y ejecuta todo el pipeline ETL + EDA.

### Outputs generados

Después de ejecutar el notebook, encontrarás en `data/processed/`:

| Archivo | Descripción | Filas aprox. |
|:--------|:------------|:-------------|
| `fact_generacion.csv` | Tabla de hechos (una fila por planta × hora × día) | ~50,000+ |
| `generacion_enriquecida.csv` | Tabla analítica con metadatos de planta | ~50,000+ |
| `dim_plantas_clean.csv` | Dimensión de plantas limpia | ~900+ |

---

## 📊 Análisis Exploratorio (EDA) — Hallazgos Clave


### Distribución por Tecnología
La generación del SIN está dominada por **hidráulica** (~65%), seguida de **térmica** (~28%). Solar representa la mayoría de los recursos registrados pero contribuye menos del 3% de la energía total, reflejando que la mayoría son instalaciones de Generación Distribuida y autogeneración de pequeña escala.

### Perfil Horario Solar–Hidráulica
La generación solar muestra una **curva de campana** con pico entre las 10h–14h. La **complementariedad** con la hidráulica es evidente: la solar reduce la demanda sobre el sistema en horas de sol, mientras la hidráulica cubre los picos nocturnos (18h–22h).

### Concentración del Mercado
El análisis de los Top 15 agentes revela alta concentración: pocos actores (EPM, EMGESA, ISAGEN) concentran la mayoría de la generación hidráulica, mientras la solar está atomizada en cientos de pequeños autogeneradores.

### Desglose por RecType (CREG)
El campo `Tipo_Recurso` revela que la mayoría de los recursos solares son `AUTOG PEQ. ESCALA` y `GEN. DISTRIBUIDA` bajo CREG 174-2021, con un marco regulatorio distinto al despacho central.
				

| RecType | Descripción | Regulación |
|:--------|:------------|:-----------|
| `AUTOG PEQ. ESCALA` | Autogeneradores < 1 MW | CREG 174-2021 |
| `GEN. DISTRIBUIDA` | Conectada a redes de distribución | CREG 174-2021 |
| `AUTOGENERADOR` | Grandes autogeneradores industriales > 1 MW | Res. CREG |
| `NORMAL` | Plantas despachadas centralmente por XM | Despacho central |
| `FILO DE AGUA` | PCH con aprovechamiento de caudal | Despacho central |

---

## 📡 Catálogo de Métricas XM

La API de XM expone **190 registros** correspondientes a **139 métricas únicas**, disponibles en 13 niveles de agregación (`Sistema`, `Agente`, `Recurso`, `Rio`, `Embalse`, etc.). Las más relevantes para el roadmap del proyecto:

| Categoría | MetricId | Unidad | Nivel | Uso en el proyecto |
|:----------|:---------|:-------|:------|:-------------------|
| **Generación** | `Gene` | kWh | Recurso | v1 ✅ — Tabla de hechos principal |
| **Demanda** | `DemaReal` | kWh | Sistema | v2 — Balance generación vs. demanda |
| **Precios** | `PrecBolsNaci` | COP/kWh | Sistema | v2 — Correlación precio-generación |
| **Embalses** | `PorcVoluUtilDiar` | % | Sistema | v2 — Seguridad hídrica |
| **Capacidad** | `CapEfecNeta` | kW | Recurso | v3 — Factor de planta real |
| **Emisiones** | `EmisionesCO2Eq` | gCO₂e/kWh | Recurso | v3 — Análisis ESG |
| **Emisiones sistema** | `factorEmisionCO2e` | gCO₂e/kWh | Sistema | v3 — Huella de carbono |
| **Solar** | `IrrGlobal` | W/m² | Recurso | v3/v5 — Performance ratio |
| **Despacho** | `GeneProgDesp` | kWh | Recurso | v5 — Desviaciones y predicción |

> El catálogo completo está disponible en `docs/Datos_API_XM.xlsx`.

---

## 🗺️ Roadmap del Proyecto

| Versión | Descripción | Estado |
|:--------|:------------|:-------|
| **v1** | ETL + EDA: pipeline reproducible, desglose por tecnología y RecType, perfil horario, concentración por agente | ✅ Completada |


---

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|:-----------|:-----------|
| Lenguaje | Python 3.10+ |
| Datos | `pydataxm`, API REST de XM |
| Manipulación | Pandas, NumPy |
| Visualización | Matplotlib, Seaborn |
| Notebook | Jupyter |
| Dashboard (v4) | Streamlit |
| ML (v5) | Scikit-learn, XGBoost |
| Despliegue (v4) | Streamlit Community Cloud |

---

## 👤 Autor

**Manuel Fernando Fajardo Rodríguez**
Senior Electrical Engineer · Power Systems · Data Science

- 8+ años de experiencia en estudios de sistemas de potencia (DIgSILENT PowerFactory, PSS/E, PSCAD, EMTP).
- 5 años ejecutando estudios de interconexión NERC/FERC para Duke Energy Florida.
- Automatización mediante Python para el sector eléctrico colombiano (CREG/CNO).
- Maestría en Ingeniería Eléctrica — Universidad Nacional de Colombia.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin)](www.linkedin.com/in/manuel-fajardo-bba988142)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?logo=github)](https://github.com/mffajardor/)

---

## 📄 Licencia

Este proyecto está bajo la [Licencia MIT](LICENSE). Los datos provienen de la API pública de XM y su uso está sujeto a los términos de XM S.A. E.S.P.
