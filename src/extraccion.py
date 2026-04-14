"""
extraccion.py
=============
Funciones para descarga de datos desde la API pública de XM (pydataxm).
Métricas soportadas: Gene (Generación Real), catálogos maestros (ListadoRecursos, etc.)

Uso:
    from src.extraccion import obtener_generacion, actualizar_catalogos_maestros
"""

import os
import time
import datetime as dt

import pandas as pd

try:
    from pydataxm import pydataxm
    API_DISPONIBLE = True
except ImportError:
    API_DISPONIBLE = False


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN REAL
# ─────────────────────────────────────────────────────────────────────────────

def obtener_generacion(fecha_inicio: dt.date, fecha_fin: dt.date) -> pd.DataFrame:
    """
    Descarga la generación real (métrica 'Gene') de todos los recursos del SIN
    desde la API de XM para el rango de fechas indicado.

    Args:
        fecha_inicio : Fecha de inicio (inclusive).
        fecha_fin    : Fecha de fin (inclusive). Máximo 31 días desde fecha_inicio.

    Returns:
        DataFrame con columnas: [Id, Values_code, Values_Hour01...Values_Hour24, Date]
        Retorna DataFrame vacío si la descarga falla o pydataxm no está instalado.
    """
    if not API_DISPONIBLE:
        print("⚠️  pydataxm no instalado. Instala con: pip install pydataxm")
        return pd.DataFrame()

    MAX_DIAS = 31
    diferencia = (fecha_fin - fecha_inicio).days

    if diferencia > MAX_DIAS:
        print(f"⚠️  Rango de {diferencia} días supera el límite. Ajustando a {MAX_DIAS} días.")
        fecha_inicio = fecha_fin - dt.timedelta(days=MAX_DIAS)

    api_xm = pydataxm.ReadDB()
    rango  = pd.date_range(start=fecha_inicio, end=fecha_fin)
    bloques = []

    print(f"🔄 Descargando 'Gene' del {fecha_inicio} al {fecha_fin} ({len(rango)} días)...")

    for fecha in rango:
        f = fecha.date()
        for intento in range(3):
            try:
                df_dia = api_xm.request_data("Gene", "Recurso", f, f)
                if df_dia is not None and not df_dia.empty:
                    bloques.append(df_dia)
                break
            except Exception as e:
                if intento < 2:
                    time.sleep(2)
                else:
                    print(f"  ❌ Falló {f} tras 3 intentos: {e}")

    if not bloques:
        print("⚠️  No se obtuvieron datos. Retornando DataFrame vacío.")
        return pd.DataFrame()

    df_total = pd.concat(bloques, ignore_index=True)
    print(
        f"✅ Descarga completa — {df_total.shape[0]:,} filas, "
        f"{df_total['Values_code'].nunique()} recursos únicos."
    )
    return df_total


def guardar_generacion(df: pd.DataFrame, directorio: str) -> str:
    """
    Guarda el DataFrame de generación en data/raw/ con timestamp en el nombre.

    Args:
        df         : DataFrame retornado por obtener_generacion().
        directorio : Ruta donde guardar el archivo (ej. 'data/raw').

    Returns:
        Ruta completa del archivo guardado.
    """
    if df.empty:
        print("⚠️  DataFrame vacío, no se guarda nada.")
        return ""

    os.makedirs(directorio, exist_ok=True)
    ts   = dt.datetime.now().strftime("%Y%m%d")
    ruta = os.path.join(directorio, f"datos_generacion_{ts}.csv")
    df.to_csv(ruta, index=False)
    print(f"💾 Datos guardados en: {ruta}")
    return ruta


# ─────────────────────────────────────────────────────────────────────────────
# CATÁLOGOS MAESTROS
# ─────────────────────────────────────────────────────────────────────────────

CATALOGOS_DEFAULT = {
    "ListadoRecursos": "dim_plantas.csv",
    "ListadoAgentes":  "dim_agentes.csv",
    "ListadoRios":     "dim_rios.csv",
}


def actualizar_catalogos_maestros(
    directorio_salida: str,
    catalogos: dict = None
) -> None:
    """
    Descarga y guarda los catálogos maestros del SIN desde la API de XM.
    Útil para mantener las dimensiones actualizadas en pipelines de producción.

    Args:
        directorio_salida : Directorio donde guardar los CSV (ej. 'data/raw').
        catalogos         : Diccionario {metrica_api: nombre_archivo.csv}.
                            Si es None, descarga los tres catálogos estándar.
    """
    if not API_DISPONIBLE:
        print("⚠️  pydataxm no instalado. Instala con: pip install pydataxm")
        return

    if catalogos is None:
        catalogos = CATALOGOS_DEFAULT

    api_xm     = pydataxm.ReadDB()
    fecha_foto = dt.date.today() - dt.timedelta(days=1)

    print(f"📋 Descargando catálogos maestros al {fecha_foto}...")
    os.makedirs(directorio_salida, exist_ok=True)

    for metrica, nombre_archivo in catalogos.items():
        try:
            df = api_xm.request_data(metrica, "Sistema", fecha_foto, fecha_foto)
            if df is not None and not df.empty:
                ruta = os.path.join(directorio_salida, nombre_archivo)
                df.to_csv(ruta, index=False)
                print(f"  ✅ {nombre_archivo:25s} → {df.shape[0]:>5} registros")
            else:
                print(f"  ⚠️  {metrica}: respuesta vacía")
        except Exception as e:
            print(f"  ❌ {metrica}: {e}")

    print("\n✅ Catálogos actualizados.")


def cargar_catalogos(directorio: str) -> dict:
    """
    Carga los catálogos maestros desde CSV (modo offline / pruebas).

    Args:
        directorio : Carpeta donde están los CSV (ej. 'data/raw' o 'data/sample').

    Returns:
        Diccionario {'plantas': df, 'agentes': df, 'rios': df}
    """
    archivos = {
        "plantas": "dim_plantas.csv",
        "agentes": "dim_agentes.csv",
        "rios":    "dim_rios.csv",
    }
    catalogos = {}
    for nombre, archivo in archivos.items():
        ruta = os.path.join(directorio, archivo)
        df   = pd.read_csv(ruta)
        catalogos[nombre] = df
        print(f"  ✅ {archivo:25s} → {df.shape[0]:>5} registros")
    return catalogos
