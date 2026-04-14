"""
etl.py
======
Funciones de transformación (ETL) para convertir los datos crudos de la API XM
al modelo relacional limpio listo para análisis y dashboards.

Pipeline:
    datos_crudos (wide)  →  transformar_generacion()  →  fact_generacion (long)
    fact_generacion      →  merge(preparar_dim_plantas()) →  generacion_enriquecida

Uso:
    from src.etl import transformar_generacion, preparar_dim_plantas, construir_modelo_relacional
"""

import os
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# TRANSFORMACIÓN DE GENERACIÓN
# ─────────────────────────────────────────────────────────────────────────────

def transformar_generacion(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Convierte los datos de generación del formato wide (24 columnas de horas)
    al formato long (una fila por planta por hora por día).

    La API de XM entrega una fila por planta por día con columnas Values_Hour01
    a Values_Hour24. Este formato es bueno para descarga pero malo para análisis.
    El melt() lo convierte al formato long estándar para series de tiempo.

    Args:
        df_raw : DataFrame crudo tal como llega de la API o del CSV.
                 Columnas esperadas: ['Date', 'Values_code', 'Values_Hour01'...'Values_Hour24']

    Returns:
        DataFrame long con columnas: ['Fecha', 'Hora', 'Codigo_Planta', 'Generacion_kWh']
        Ordenado por Fecha → Codigo_Planta → Hora.
    """
    cols_hora = [c for c in df_raw.columns if c.startswith("Values_Hour")]
    assert len(cols_hora) == 24, (
        f"Se esperaban 24 columnas horarias, se encontraron {len(cols_hora)}. "
        f"Columnas encontradas: {cols_hora}"
    )

    # PASO 1 — Melt: wide → long
    df_long = pd.melt(
        df_raw,
        id_vars=["Date", "Values_code"],
        value_vars=cols_hora,
        var_name="Hora_Cruda",
        value_name="Generacion_kWh"
    )

    # PASO 2 — Extraer número de hora limpio: 'Values_Hour03' → 3
    df_long["Hora"] = (
        df_long["Hora_Cruda"]
        .str.replace("Values_Hour", "", regex=False)
        .astype(int)
    )

    # PASO 3 — Renombrar a nombres semánticos
    df_long = df_long.rename(columns={
        "Date":        "Fecha",
        "Values_code": "Codigo_Planta"
    })

    # PASO 4 — Limpiar, ordenar y tipar
    df_long = (
        df_long
        .drop(columns=["Hora_Cruda"])
        .sort_values(["Fecha", "Codigo_Planta", "Hora"])
        .reset_index(drop=True)
    )
    df_long["Fecha"]          = pd.to_datetime(df_long["Fecha"])
    df_long["Generacion_kWh"] = df_long["Generacion_kWh"].astype(float)

    return df_long[["Fecha", "Hora", "Codigo_Planta", "Generacion_kWh"]]


# ─────────────────────────────────────────────────────────────────────────────
# PREPARACIÓN DE DIMENSIONES
# ─────────────────────────────────────────────────────────────────────────────

# Mapeo canónico: nombres de la API → nombres semánticos del modelo
MAPA_COLUMNAS_PLANTAS = {
    "Values_Code":          "Codigo_Planta",
    "Values_Name":          "Nombre_Planta",
    "Values_Type":          "Tecnologia",
    "Values_EnerSource":    "Fuente_Energia",
    "Values_CompanyCode":   "Codigo_Agente",
    "Values_Disp":          "Tipo_Despacho",
    "Values_RecType":       "Tipo_Recurso",
    "Values_OperStartdate": "Fecha_Inicio_Op",
    "Values_State":         "Estado",
}


def preparar_dim_plantas(df_dim: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y renombra la dimensión de plantas para facilitar JOINs y análisis.

    Args:
        df_dim : DataFrame crudo de dim_plantas.csv

    Returns:
        DataFrame limpio con columnas renombradas y sin columnas auxiliares de la API
        (Id, Date).
    """
    return (
        df_dim
        .rename(columns=MAPA_COLUMNAS_PLANTAS)
        .drop(columns=["Id", "Date"], errors="ignore")
        [list(MAPA_COLUMNAS_PLANTAS.values())]
    )


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE COMPLETO
# ─────────────────────────────────────────────────────────────────────────────

def construir_modelo_relacional(
    df_raw: pd.DataFrame,
    df_dim_plantas: pd.DataFrame,
    directorio_salida: str = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Ejecuta el pipeline ETL completo y opcionalmente guarda los resultados.

    Pipeline:
        1. transformar_generacion()  → fact_generacion (long)
        2. preparar_dim_plantas()    → dim_plantas limpia
        3. merge()                   → generacion_enriquecida
        4. Verificación de integridad del JOIN
        5. Guardado opcional en directorio_salida

    Args:
        df_raw             : DataFrame crudo de generación (formato wide de la API).
        df_dim_plantas     : DataFrame crudo de dim_plantas.csv
        directorio_salida  : Si se provee, guarda los CSVs procesados aquí.

    Returns:
        Tupla (fact_generacion, generacion_enriquecida)
    """
    print("🔧 Ejecutando pipeline ETL...")

    # Paso 1 — Transformar
    fact_gen = transformar_generacion(df_raw)
    print(f"  ✅ fact_generacion:     {fact_gen.shape[0]:>7,} filas × {fact_gen.shape[1]} columnas")

    # Paso 2 — Preparar dimensión
    dim_plantas = preparar_dim_plantas(df_dim_plantas)
    print(f"  ✅ dim_plantas:         {dim_plantas.shape[0]:>7,} plantas en el catálogo")

    # Paso 3 — JOIN
    gen_enriquecida = pd.merge(fact_gen, dim_plantas, on="Codigo_Planta", how="inner")
    print(f"  ✅ gen_enriquecida:     {gen_enriquecida.shape[0]:>7,} filas × {gen_enriquecida.shape[1]} columnas")

    # Paso 4 — Verificación de integridad
    plantas_sin_match = set(fact_gen["Codigo_Planta"]) - set(dim_plantas["Codigo_Planta"])
    if plantas_sin_match:
        print(f"  ⚠️  {len(plantas_sin_match)} plantas sin match en dim_plantas: {plantas_sin_match}")
    else:
        print("  ✅ Integridad OK — todas las plantas tienen match en dim_plantas.")

    # Paso 5 — Guardado opcional
    if directorio_salida:
        os.makedirs(directorio_salida, exist_ok=True)
        fact_gen.to_csv(os.path.join(directorio_salida, "fact_generacion.csv"), index=False)
        gen_enriquecida.to_csv(os.path.join(directorio_salida, "generacion_enriquecida.csv"), index=False)
        dim_plantas.to_csv(os.path.join(directorio_salida, "dim_plantas_clean.csv"), index=False)
        print(f"\n  💾 Archivos guardados en: {directorio_salida}")

    print("\n✅ ETL completado.")
    return fact_gen, gen_enriquecida
