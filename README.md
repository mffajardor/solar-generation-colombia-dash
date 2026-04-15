# 🇨🇴 Proyecto de Análisis de Generación Eléctrica — Colombia mediante la API de XM

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
- [Instalación y Configuración](#-instalación-y-configuración)
- [Uso](#-uso)
- [Análisis Exploratorio (EDA) — Hallazgos Clave](#-análisis-exploratorio-eda--hallazgos-clave)
- [Catálogo de Métricas XM](#-catálogo-de-métricas-xm)
- [Roadmap del Proyecto](#-roadmap-del-proyecto)
- [Stack Tecnológico](#-stack-tecnológico)
- [Autor](#-autor)
- [Licencia](#-licencia)

---


## 🎯 Descripción del Proyecto

Este proyecto construye un **pipeline ETL (Extract–Transform–Load) reproducible** que extrae datos consolidados del sector de generación eléctrica en tiempo real desde la API pública de XM — el operador del mercado eléctrico de Colombia — realizando su respectiva transformación en un **modelo dimensional limpio** (star schema), y entrega un análisis exploratorio del parque generador del Sistema Interconectado Nacional (SIN).


### Preguntas que responde

1. **¿Cómo es la distribución de la generación del SIN por tecnología?** — Participación porcentual de Solar, Hidráulica, Térmica, Eólica y Cogeneración en la generación total del SIN.
2. **¿Cuál es el perfil horario típico de generación solar en Colombia?** — Se maneja tipicamente una Curva de campana (bell curve) H1–H24, la cual se complementa con la generación hidráulica.
3. **¿Qué tan concentrado está el mercado por agente generador?** — Análisis de los agentes más grandes (top 15), participación por tecnología e indicadores de concentración.
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

XM presenta una **API REST pública** la cual permite consultar diferentes fuentes de datos tanto operativos como comerciales del SIN. Dicho uso no requiere de autenticación (API key), pero tiene las siguientes restricciones:

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