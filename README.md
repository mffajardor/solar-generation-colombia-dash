# 🇨🇴 Análisis del Sistema Eléctrico Colombiano — API XM

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Pandas](https://img.shields.io/badge/Pandas-2.x-150458?logo=pandas)](https://pandas.pydata.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-v2%20definitiva%20en%20revisi%C3%B3n-2E7D32)]()

> Pipeline ETL reproducible y análisis del Sistema Interconectado Nacional (SIN)
> a partir de la API pública de XM: generación, demanda, precio de bolsa,
> embalses y aportes hídricos.

---

## 📋 Contenido

- [Descripción](#-descripción)
- [Versiones del proyecto](#-versiones-del-proyecto)
- [Preguntas de análisis](#-preguntas-de-análisis)
- [Fuentes y métricas XM](#-fuentes-y-métricas-xm)
- [Arquitectura de datos](#-arquitectura-de-datos)
- [Estructura del repositorio](#-estructura-del-repositorio)
- [Instalación](#-instalación)
- [Ejecución](#-ejecución)
- [Outputs de la v2](#-outputs-de-la-v2)
- [Análisis incluidos](#-análisis-incluidos)
- [Calidad y reproducibilidad](#-calidad-y-reproducibilidad)
- [Estado de validación](#-estado-de-validación)
- [Roadmap](#-roadmap)
- [Autor](#-autor)
- [Licencia y fuentes oficiales](#-licencia-y-fuentes-oficiales)

---

## 🎯 Descripción

Este proyecto analiza información pública del mercado eléctrico colombiano
administrada por **XM S.A. E.S.P.**, operador del SIN y administrador del Mercado
de Energía Mayorista (MEM).

El flujo:

1. Extrae métricas desde la API de XM o carga snapshots CSV.
2. Valida cobertura temporal, estructura, nulos, rangos y duplicados.
3. Transforma las 24 columnas horarias de XM de formato ancho a largo.
4. Enriquece la generación con catálogos de plantas y agentes.
5. Construye tablas horarias y diarias del sistema.
6. Complementa cada planta con áreas operativas SIMEM y geografía UPME/XM.
7. Genera análisis energéticos, económicos, hídricos y territoriales.
8. Exporta tablas y figuras reproducibles para análisis posteriores.

El repositorio se desarrolla por versiones. La **v1** establece el ETL y EDA de
generación; la **v2** amplía el modelo hacia una visión integrada de la operación
del SIN.

---

## 🧭 Versiones del proyecto

### v1 — ETL y análisis exploratorio de generación

Incluye:

- generación real por recurso;
- transformación `wide → long`;
- dimensión de plantas y agentes;
- distribución por tecnología;
- perfil horario solar e hidráulico;
- concentración por agente;
- clasificación por tipo de recurso.

### v2 — Series de tiempo y contexto operativo

Añade:

- demanda real horaria;
- precio de bolsa nacional;
- precio de escasez como referencia;
- nivel diario de embalses;
- aportes hídricos;
- balance analítico generación–demanda;
- asociaciones precio–embalses–participación térmica;
- figuras unificadas y separadas para facilitar su lectura;
- heatmaps y perfiles horarios alternativos;
- áreas y subáreas operativas obtenidas de SIMEM;
- departamento, municipio y coordenadas obtenidos de la capa UPME/XM;
- comparación auditable de cobertura entre SIMEM y UPME;
- exploradores interactivos operativo y geográfico;
- perfil solar y demanda para días laborables y fines de semana;
- indicadores exploratorios para la futura v2.5 sobre SAEB.

> **Estado:** la implementación definitiva candidata de v2 fue validada con las
> seis métricas del período 2026-05-10 a 2026-06-07. La unión de los catálogos
> SIMEM y UPME identifica las 506 plantas presentes en la generación del período,
> sin eliminar registros sin correspondencia individual. Falta únicamente la
> revisión final del autor antes de etiquetarla como `v2.0.0`.

---

## ❓ Preguntas de análisis

### Preguntas de v1

1. ¿Cómo se distribuye la generación por tecnología?
2. ¿Cuál es el perfil horario de la generación solar?
3. ¿Qué agentes concentran la generación?
4. ¿Cómo se compone el parque solar por tipo de recurso?

### Preguntas de v2

1. ¿Cómo evolucionan generación y demanda durante el período analizado?
2. ¿En qué horas aparece el menor gap entre generación reportada y demanda?
3. ¿Cómo cambia el precio de bolsa dentro del día?
4. ¿Qué asociación presentan precio, embalses y participación térmica?
5. ¿Cómo evolucionan los aportes hídricos y el nivel de embalses?
6. ¿Existe un spread horario que justifique estudiar almacenamiento con baterías?

El gap `Gene - DemaReal` se utiliza como indicador analítico y de consistencia.
No representa automáticamente exportaciones o déficit físico, pues puede recoger
pérdidas, intercambios, diferencias de cobertura y convenciones de liquidación.

---

## 📡 Fuentes y métricas XM

| Categoría | MetricId | Entidad | Frecuencia | Unidad del catálogo | Versión |
|:--|:--|:--|:--|:--|:--|
| Generación real | `Gene` | Recurso | Horaria | kWh | v1/v2 |
| Demanda real | `DemaReal` | Sistema | Horaria | kWh | v2 |
| Precio de bolsa | `PrecBolsNaci` | Sistema | Horaria | COP/kWh | v2 |
| Volumen útil | `PorcVoluUtilDiar` | Sistema | Diaria | % | v2 |
| Aportes hídricos | `AporEner` | Sistema | Diaria | kWh | v2 |
| Precio de escasez | `PrecEsca` | Sistema | Diaria | COP/kWh | v2 |

La API limita las consultas de estas métricas a ventanas de hasta 31 días. La v2
divide automáticamente períodos mayores en bloques y aplica reintentos.

Aunque el catálogo expresa `PorcVoluUtilDiar` en porcentaje, el endpoint diario
puede entregar una fracción entre 0 y 1. El ETL detecta ese caso y normaliza, por
ejemplo, `0.7045 → 70.45%`.

---

## 🔧 Arquitectura de datos

```text
API XM / CSV
     │
     ▼
datos_crudos (formato ancho: Values_Hour01 ... Values_Hour24)
     │
     ├── validación de cobertura, estructura y calidad
     │
     ▼
tablas de hechos en formato largo
     │
     ├── fact_generacion
     ├── fact_demanda
     ├── fact_precio
     ├── fact_embalses
     ├── fact_aportes
     └── fact_precio_escasez
     │
     ├── merge con dim_plantas
     ▼
gen_enriquecida
     │
     ├── agregación horaria
     ▼
sistema_h
     │
     ├── agregación diaria
     ▼
resumen_diario ──► gráficos, hallazgos y preparación de v2.5
```

### Grano de las tablas

| Tabla | Una fila representa |
|:--|:--|
| `fact_generacion` | Recurso × fecha × hora XM |
| `fact_demanda` | Sistema × fecha × hora XM |
| `fact_precio` | Sistema × fecha × hora XM |
| `fact_embalses` | Sistema × fecha |
| `fact_aportes` | Sistema × fecha |
| `sistema_h` | Una hora consolidada del SIN |
| `resumen_diario` | Un día consolidado del SIN |

En la convención de XM, `H01` representa el intervalo 00:00–01:00.

---

## 📂 Estructura del repositorio

```text
solar-generation-colombia-dash/
│
├── notebooks/
│   ├── 01_ETL_exploracion_v1.ipynb
│   └── 02_serie_tiempo_balance_v2.ipynb
│
├── docs/
│   └── GUIA_ESTUDIO_V2.md
│
├── src/
│   ├── extraccion.py
│   ├── etl.py
│   ├── visualizaciones.py
│   ├── actualizar_areas_operativas_simem.py
│   └── actualizar_catalogo_plantas.py
│
├── data/
│   ├── raw/                 # No versionar: snapshots descargados
│   ├── processed/           # No versionar: tablas y figuras regenerables
│   └── reference/           # Dimensiones pequeñas y reproducibles
│
├── app/                     # Dashboard Streamlit planificado para v4
├── 00_Prev/                 # Borradores y propuestas; no publicar completo
├── requirements.txt
├── .gitignore
└── README.md
```

`00_Prev/` funciona como espacio de revisión. Solo las versiones aprobadas deben
promoverse a `notebooks/`, `docs/` o a los archivos raíz.

---

## ⚙️ Instalación

### Requisitos

- Python 3.10 o superior.
- `pip`.
- Jupyter Notebook, JupyterLab o VS Code con soporte para notebooks.

### Preparación

```bash
git clone https://github.com/mffajardor/solar-generation-colombia-dash.git
cd solar-generation-colombia-dash

python -m venv .venv
```

Activación:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate
```

Instalación:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Dependencias propuestas para v2:

```text
pydataxm>=0.3.18
pandas>=2.0
numpy>=1.24
requests>=2.31
matplotlib>=3.7
seaborn>=0.12
ipywidgets>=8.0
```

La v2 usa el catálogo de `pydataxm` y realiza la descarga mediante los endpoints
REST de XM con `requests`, lo que evita incompatibilidades del método asíncrono de
algunas versiones de `pydataxm` en Python 3.14.

---

## 🚀 Ejecución

### 1. Ejecutar la v1

```bash
jupyter notebook notebooks/01_ETL_exploracion_v1.ipynb
```

La v1 prepara la generación y los catálogos maestros.

### 2. Ejecutar la v2

```bash
jupyter notebook notebooks/02_serie_tiempo_balance_v2.ipynb
```

Seleccionar un modo en la celda de configuración:

```python
MODO = "API"   # Últimos N días cerrados hasta D-1
MODO = "FIJO"  # Período histórico definido por el usuario
MODO = "CSV"   # Snapshots existentes; no requiere conexión
```

#### Modo API

Descarga las métricas necesarias y guarda snapshots en `data/raw/`.

#### Modo FIJO

Permite reproducir un período concreto:

```python
FECHA_INICIO_FIJO = dt.date(2026, 5, 1)
FECHA_FIN_FIJO = dt.date(2026, 5, 31)
```

#### Modo CSV

Carga el archivo más reciente de cada prefijo. El período analítico corresponde
a la **intersección de fechas** disponible entre las métricas, no a su unión.

---

## 📦 Outputs de la v2

Las tablas se escriben en `data/processed/` con una etiqueta de período:

```text
{tabla}_{YYYYMMDD}_{YYYYMMDD}.csv
```

| Output | Contenido |
|:--|:--|
| `fact_generacion_*` | Generación horaria por recurso |
| `fact_demanda_*` | Demanda horaria del sistema |
| `fact_precio_*` | Precio de bolsa horario |
| `fact_embalses_*` | Nivel diario de embalses normalizado a % |
| `fact_aportes_*` | Aportes hídricos diarios |
| `fact_precio_escasez_*` | Referencia diaria de precio de escasez |
| `gen_enriquecida_*` | Generación con metadatos de planta |
| `sistema_h_*` | Vista horaria consolidada |
| `resumen_diario_*` | Vista diaria consolidada |
| `hallazgos_v2_*` | Indicadores calculados para el período |
| `dim_plantas_areas_operativas.csv` | Planta → área/subárea operativa SIMEM |
| `dim_plantas_geografia_upme.csv` | Planta → departamento/municipio/coordenadas |
| `dim_plantas_operativa_geografica.csv` | Catálogo combinado sin mezclar conceptos |
| `qc_cobertura_fuentes_*` | Comparación de cobertura SIMEM, UPME y unión |
| `qc_detalle_cobertura_fuentes_*` | Trazabilidad por Código SIC |

Las figuras se guardan en `data/processed/figuras_v2/`.

---

## 📊 Análisis incluidos

### v1

- participación por tecnología;
- perfil horario solar–hidráulico;
- principales agentes generadores;
- composición por tipo de recurso;
- evolución diaria de generación.

### v2

1. Balance diario generación–demanda.
2. Perfil horario del gap.
3. Serie de precio con rango mínimo–máximo.
4. Asociación precio–embalses.
5. Asociación precio–participación térmica.
6. Perfil horario de precios y spread pico–valle.
7. Nivel de embalses con bandas analíticas configurables.
8. Aportes hídricos y cambio diario de embalses.
9. Heatmap tecnología × hora.
10. Heatmap precio día × hora.
11. Perfil solar laborable vs. fin de semana.
12. Perfil comparado de generación solar y demanda por tipo de día.
13. Generación por área y subárea operativa SIMEM.
14. Comparación de cobertura SIMEM–UPME.
15. Generación por región, departamento o municipio.
16. Resumen cuantitativo generado desde los datos ejecutados.

Las correlaciones son exploratorias y no demuestran causalidad. Las bandas de
embalses usadas en los gráficos tampoco equivalen a alertas regulatorias.

---

## ✅ Calidad y reproducibilidad

La v2 incorpora:

- descarga por bloques de máximo 31 días;
- tres reintentos ante fallos de red;
- selección de archivos por patrón, sin nombres hardcodeados;
- período común entre métricas;
- validación de fechas solicitadas y obtenidas;
- reporte de nulos horarios;
- validación de valores negativos y embalses fuera de 0–100%;
- detección de duplicados en el grano;
- deduplicación de `dim_plantas` antes del merge;
- `left join` para conservar recursos sin catálogo;
- validación de unicidad del Código SIC en cada fuente;
- separación explícita entre región geográfica y área operativa;
- paginación de la capa REST UPME;
- caché auditable y reutilizable para SIMEM y UPME;
- cobertura calculada por número de plantas y por energía;
- rutas relativas a la raíz del repositorio;
- outputs y figuras con etiqueta del período;
- ejecución degradada controlada cuando faltan métricas en modo CSV.

Los valores nulos de generación se reportan y conservan para no eliminar
silenciosamente combinaciones recurso×fecha×hora.

---

## 🧪 Estado de validación

La versión definitiva candidata de v2 ha superado:

- compilación de todas las celdas;
- ejecución offline con los CSV de generación disponibles;
- ejecución integral con datos de prueba que reproducen los esquemas de XM;
- validación de los esquemas reales de las cinco métricas nuevas;
- consultas REST de las métricas XM y de la capa geográfica UPME/XM;
- validación de la conversión de embalses de fracción a porcentaje;
- generación de tablas, figuras y hallazgos dinámicos;
- cruce exacto de 404/506 plantas con SIMEM;
- cruce exacto de 500/506 plantas con UPME;
- cobertura conjunta de 506/506 plantas;
- conservación del 100 % de los registros de generación analizados.

Antes de publicar `v2.0.0`, el autor debe revisar visualmente el notebook
principal y aprobar la secuencia de commits propuesta en `00_Prev/`.

---

## 🗺️ Roadmap

| Versión | Alcance | Estado |
|:--|:--|:--|
| **v1** | ETL + EDA de generación y catálogos | ✅ Completada |
| **v2** | Series, contexto operativo y cobertura territorial | 🔎 Definitiva en revisión |
| **v2.5** | Simulación y caso de negocio SAEB | 📐 Diseñada |
| **v3** | Capacidad, factor de planta y emisiones | 📋 Planeada |
| **v4** | Dashboard interactivo Streamlit | 📋 Planeada |
| **v5** | Desviaciones y modelos predictivos | 📋 Planeada |

### Preparación para v2.5

La v2 calcula:

```text
spread_bruto = precio_pico - precio_valle
spread_ajustado = precio_pico - precio_valle / eficiencia_round_trip
```

Estos indicadores solo justifican continuar el estudio. La viabilidad de un SAEB
requiere modelar estado de carga, potencia, energía, eficiencia, degradación,
CAPEX, OPEX, conexión, liquidación y reglas de participación.

La referencia regulatoria utilizada es la **Resolución CREG 101 113 de 2026**,
que define reglas para la instalación, operación y aspectos comerciales de los
SAEB en el SIN.

---

## 🛠️ Stack tecnológico

| Componente | Tecnología |
|:--|:--|
| Lenguaje | Python 3.10+ |
| Datos | API REST de XM, `pydataxm`, `requests` |
| Transformación | Pandas, NumPy |
| Visualización | Matplotlib, Seaborn |
| Desarrollo | Jupyter Notebook / VS Code |
| Dashboard futuro | Streamlit |
| Modelos futuros | Scikit-learn, XGBoost |

---

## 👤 Autor

**Manuel Fernando Fajardo Rodríguez**  
Senior Electrical Engineer · Power Systems · Data Science

- Experiencia en estudios de sistemas de potencia.
- Automatización y análisis de datos para el sector eléctrico.
- Maestría en Ingeniería Eléctrica — Universidad Nacional de Colombia.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin)](https://www.linkedin.com/in/manuel-fajardo-bba988142)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-181717?logo=github)](https://github.com/mffajardor/)

---

## 📄 Licencia y fuentes oficiales

Este proyecto está bajo la [Licencia MIT](LICENSE).

Los datos provienen de fuentes públicas de XM y deben interpretarse según sus
definiciones y condiciones vigentes:

- [XM — servicios de información](https://www.xm.com.co/servicios-de-informacion)
- [XM — precio de bolsa y precio de escasez](https://www.xm.com.co/transacciones/cargo-por-confiabilidad/precio-de-bolsa-y-escasez)
- [CREG — Resolución 101 113 de 2026](https://gestornormativo.creg.gov.co/gestor/entorno/docs/resolucion_creg_101-113_2026.htm)

Este repositorio tiene fines educativos y analíticos. No constituye una
recomendación de inversión ni reemplaza información operativa o regulatoria
oficial.
