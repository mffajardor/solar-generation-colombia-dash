"""Integra la cobertura operativa de SIMEM con la geografía pública de UPME.

La unión se realiza exclusivamente por el código SIC de la planta:

    SIMEM.Codigo_Planta == UPME.codigo_sic

SIMEM conserva la autoridad sobre área y subárea operativa. UPME se utiliza
como fuente complementaria para departamento, municipio, coordenadas y
atributos descriptivos del recurso. Las dos clasificaciones nunca se mezclan.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


UPME_LAYER_URL = (
    "https://geo.upme.gov.co/server/rest/services/"
    "Capas_EnergiaElectrica/proyectos_generacion_xm/FeatureServer/24"
)
UPME_QUERY_URL = f"{UPME_LAYER_URL}/query"
UPME_PAGE_SIZE = 2000

REGIONES_GEOGRAFICAS = {
    "Antioquia": {"ANTIOQUIA"},
    "Caribe": {
        "ATLÁNTICO",
        "BOLÍVAR",
        "CESAR",
        "CÓRDOBA",
        "LA GUAJIRA",
        "MAGDALENA",
        "SUCRE",
        "SAN ANDRÉS Y PROVIDENCIA",
    },
    "Centro": {
        "BOGOTÁ. D.C.",
        "BOYACÁ",
        "CUNDINAMARCA",
        "HUILA",
        "TOLIMA",
    },
    "Eje Cafetero": {"CALDAS", "QUINDIO", "QUINDÍO", "RISARALDA"},
    "Oriente": {
        "ARAUCA",
        "CASANARE",
        "META",
        "NORTE DE SANTANDER",
        "SANTANDER",
    },
    "Pacífico": {"CAUCA", "NARIÑO", "VALLE DEL CAUCA"},
    "Amazonía": {
        "AMAZONAS",
        "CAQUETÁ",
        "GUAINÍA",
        "GUAVIARE",
        "PUTUMAYO",
        "VAUPÉS",
    },
}


def crear_sesion() -> requests.Session:
    """Crea una sesión HTTP con reintentos ante fallos temporales."""
    reintentos = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    sesion = requests.Session()
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    sesion.headers.update(
        {"User-Agent": "solar-generation-colombia-dash/2.3"}
    )
    return sesion


def _region_geografica(departamento: Any) -> str:
    if pd.isna(departamento):
        return "Sin asignar"
    nombre = str(departamento).strip().upper()
    for region, departamentos in REGIONES_GEOGRAFICAS.items():
        if nombre in departamentos:
            return region
    return "Otra región"


def _fecha_arcgis_bogota(serie: pd.Series) -> pd.Series:
    """Convierte milisegundos ArcGIS a fecha civil de Colombia."""
    fecha = pd.to_datetime(serie, unit="ms", errors="coerce", utc=True)
    return fecha.dt.tz_convert("America/Bogota").dt.strftime("%Y-%m-%d")


def descargar_upme(
    sesion: requests.Session | None = None,
    page_size: int = UPME_PAGE_SIZE,
    timeout: int = 120,
) -> dict[str, Any]:
    """Descarga todas las entidades de la capa usando paginación."""
    sesion = sesion or crear_sesion()
    metadatos = sesion.get(
        UPME_LAYER_URL,
        params={"f": "json"},
        timeout=timeout,
    )
    metadatos.raise_for_status()
    metadata_payload = metadatos.json()
    if "error" in metadata_payload:
        raise RuntimeError(f"UPME devolvió error: {metadata_payload['error']}")
    if "Query" not in str(metadata_payload.get("capabilities", "")):
        raise RuntimeError("La capa UPME no anuncia la capacidad Query.")

    total_response = sesion.get(
        UPME_QUERY_URL,
        params={"f": "json", "where": "1=1", "returnCountOnly": "true"},
        timeout=timeout,
    )
    total_response.raise_for_status()
    total = int(total_response.json().get("count", 0))

    features: list[dict[str, Any]] = []
    offset = 0
    while offset < total:
        response = sesion.get(
            UPME_QUERY_URL,
            params={
                "f": "json",
                "where": "1=1",
                "outFields": "*",
                "returnGeometry": "true",
                "outSR": "4326",
                "orderByFields": metadata_payload.get("objectIdField", "id"),
                "resultOffset": offset,
                "resultRecordCount": page_size,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"UPME devolvió error: {payload['error']}")
        lote = payload.get("features", [])
        if not lote:
            break
        features.extend(lote)
        offset += len(lote)

    if len(features) != total:
        raise RuntimeError(
            f"Descarga UPME incompleta: se esperaban {total} registros "
            f"y se recibieron {len(features)}."
        )
    return {
        "source": UPME_LAYER_URL,
        "download_date": date.today().isoformat(),
        "spatialReference": {"wkid": 4326},
        "features": features,
    }


def normalizar_upme(payload: dict[str, Any]) -> pd.DataFrame:
    """Convierte atributos y geometrías ArcGIS en una dimensión tabular."""
    filas: list[dict[str, Any]] = []
    for feature in payload.get("features", []):
        fila = dict(feature.get("attributes") or {})
        geometria = feature.get("geometry") or {}
        fila["Longitud"] = geometria.get("x")
        fila["Latitud"] = geometria.get("y")
        filas.append(fila)
    datos = pd.DataFrame.from_records(filas)

    requeridas = {
        "codigo_sic",
        "nombre_recurso",
        "departamento_oficial",
        "municipio_oficial",
        "cod_mpio",
    }
    faltantes = requeridas.difference(datos.columns)
    if faltantes:
        raise ValueError(
            f"La capa UPME no contiene las columnas requeridas: "
            f"{sorted(faltantes)}"
        )

    datos["codigo_sic"] = (
        datos["codigo_sic"].astype("string").str.strip().str.upper()
    )
    datos = datos.dropna(subset=["codigo_sic"])
    duplicados = datos.loc[
        datos["codigo_sic"].duplicated(keep=False), "codigo_sic"
    ].unique()
    if len(duplicados):
        raise ValueError(
            "UPME contiene códigos SIC duplicados: "
            + ", ".join(map(str, duplicados[:10]))
        )

    for columna in ("fecha_operacion", "fecha"):
        if columna in datos.columns:
            datos[columna] = _fecha_arcgis_bogota(datos[columna])

    datos["Region_Geografica"] = datos["departamento_oficial"].map(
        _region_geografica
    )
    renombres = {
        "codigo_sic": "Codigo_Planta",
        "nombre_recurso": "Nombre_Recurso_UPME",
        "capacidad_efectiva_neta_mw": "Capacidad_Efectiva_MW",
        "factor_conversion": "Factor_Conversion",
        "es_menor": "Es_Menor",
        "tipo_despacho": "Tipo_Despacho_UPME",
        "combustible_defecto": "Combustible_UPME",
        "fecha_operacion": "Fecha_Operacion_UPME",
        "agente_representante": "Agente_Representante_UPME",
        "estado_recurso": "Estado_Recurso_UPME",
        "tipo_generacion": "Tipo_Generacion_UPME",
        "clasificacion": "Clasificacion_UPME",
        "fecha": "Fecha_Actualizacion_UPME",
        "municipio_oficial": "Municipio",
        "cod_mpio": "Codigo_Municipio",
        "departamento_oficial": "Departamento",
        "anio_fpo": "Anio_FPO_UPME",
        "id": "Id_UPME",
    }
    datos = datos.rename(columns=renombres)
    orden = [
        "Codigo_Planta",
        "Nombre_Recurso_UPME",
        "Departamento",
        "Codigo_Municipio",
        "Municipio",
        "Region_Geografica",
        "Longitud",
        "Latitud",
        "Capacidad_Efectiva_MW",
        "Tipo_Generacion_UPME",
        "Combustible_UPME",
        "Tipo_Despacho_UPME",
        "Clasificacion_UPME",
        "Estado_Recurso_UPME",
        "Agente_Representante_UPME",
        "Fecha_Operacion_UPME",
        "Anio_FPO_UPME",
        "Fecha_Actualizacion_UPME",
        "Factor_Conversion",
        "Es_Menor",
        "Id_UPME",
    ]
    columnas = [columna for columna in orden if columna in datos.columns]
    return datos[columnas].sort_values("Codigo_Planta").reset_index(drop=True)


def cargar_o_actualizar_upme(
    base_dir: Path,
    actualizar: bool = False,
) -> pd.DataFrame:
    """Reutiliza la dimensión local o descarga nuevamente la capa UPME."""
    raw_dir = base_dir / "data" / "raw" / "upme"
    reference_dir = base_dir / "data" / "reference"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)
    salida = reference_dir / "dim_plantas_geografia_upme.csv"

    if salida.exists() and not actualizar:
        print(f"Se reutiliza la dimensión UPME: {salida}")
        return pd.read_csv(salida, dtype={"Codigo_Planta": "string"})

    candidatos_cache = sorted(
        raw_dir.glob("upme_proyectos_generacion_xm_*.json"),
        reverse=True,
    )
    if candidatos_cache and not actualizar:
        cache_path = candidatos_cache[0]
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        print(f"Se reutiliza la respuesta UPME: {cache_path.name}")
    else:
        try:
            payload = descargar_upme()
        except requests.RequestException as exc:
            if not candidatos_cache:
                raise RuntimeError(
                    "No fue posible consultar UPME y no existe una respuesta "
                    "local. Revisa la conexión y el almacén de certificados "
                    "HTTPS de Python."
                ) from exc
            cache_path = candidatos_cache[0]
            print(
                "Advertencia: no fue posible actualizar UPME; "
                f"se reutiliza {cache_path.name}."
            )
            payload = json.loads(cache_path.read_text(encoding="utf-8"))

    etiqueta = date.today().strftime("%Y%m%d")
    raw_path = raw_dir / f"upme_proyectos_generacion_xm_{etiqueta}.json"
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    dimension = normalizar_upme(payload)
    dimension.to_csv(salida, index=False)
    print(f"UPME: {len(dimension):,} recursos descargados.")
    print(f"Respuesta original: {raw_path}")
    print(f"Dimensión geográfica: {salida}")
    return dimension


def integrar_dimensiones(
    simem: pd.DataFrame,
    upme: pd.DataFrame,
) -> pd.DataFrame:
    """Construye el catálogo completo sin confundir geografía y operación."""
    for nombre, datos in (("SIMEM", simem), ("UPME", upme)):
        if "Codigo_Planta" not in datos.columns:
            raise ValueError(f"{nombre}: falta la columna Codigo_Planta.")
        if datos["Codigo_Planta"].duplicated().any():
            raise ValueError(f"{nombre}: Codigo_Planta no es único.")

    simem = simem.copy()
    upme = upme.copy()
    simem["Codigo_Planta"] = (
        simem["Codigo_Planta"].astype("string").str.strip().str.upper()
    )
    upme["Codigo_Planta"] = (
        upme["Codigo_Planta"].astype("string").str.strip().str.upper()
    )
    simem["_En_SIMEM"] = True
    upme["_En_UPME"] = True
    catalogo = simem.merge(
        upme,
        on="Codigo_Planta",
        how="outer",
        validate="one_to_one",
    )
    catalogo["En_SIMEM"] = catalogo.pop("_En_SIMEM").eq(True)
    catalogo["En_UPME"] = catalogo.pop("_En_UPME").eq(True)
    catalogo["Fuente_Cobertura"] = "Ninguna"
    catalogo.loc[catalogo["En_SIMEM"], "Fuente_Cobertura"] = "Solo SIMEM"
    catalogo.loc[catalogo["En_UPME"], "Fuente_Cobertura"] = "Solo UPME"
    catalogo.loc[
        catalogo["En_SIMEM"] & catalogo["En_UPME"], "Fuente_Cobertura"
    ] = "SIMEM + UPME"
    return catalogo.sort_values("Codigo_Planta").reset_index(drop=True)


def auditar_cobertura(
    generacion: pd.DataFrame,
    catalogo: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Calcula cobertura por planta y energía para SIMEM, UPME y su unión."""
    requeridas = {"Codigo_Planta", "Generacion_kWh"}
    faltantes = requeridas.difference(generacion.columns)
    if faltantes:
        raise ValueError(
            f"Generación: faltan columnas obligatorias {sorted(faltantes)}"
        )

    energia = generacion[["Codigo_Planta", "Generacion_kWh"]].copy()
    energia["Codigo_Planta"] = (
        energia["Codigo_Planta"].astype("string").str.strip().str.upper()
    )
    energia["Generacion_kWh"] = pd.to_numeric(
        energia["Generacion_kWh"], errors="coerce"
    )
    energia = (
        energia.groupby("Codigo_Planta", as_index=False)["Generacion_kWh"]
        .sum(min_count=1)
    )
    detalle = energia.merge(
        catalogo[
            [
                "Codigo_Planta",
                "En_SIMEM",
                "En_UPME",
                "Fuente_Cobertura",
                "Area_Operativa",
                "Subarea_Operativa",
                "Region_Geografica",
                "Departamento",
                "Municipio",
            ]
        ],
        on="Codigo_Planta",
        how="left",
        validate="one_to_one",
    )
    detalle["En_SIMEM"] = detalle["En_SIMEM"].fillna(False).astype(bool)
    detalle["En_UPME"] = detalle["En_UPME"].fillna(False).astype(bool)
    detalle["En_Union"] = detalle["En_SIMEM"] | detalle["En_UPME"]

    filas = []
    total_plantas = len(detalle)
    total_energia = detalle["Generacion_kWh"].sum()
    for fuente, columna in (
        ("SIMEM — cobertura operativa", "En_SIMEM"),
        ("UPME — cobertura geográfica", "En_UPME"),
        ("Unión de catálogos", "En_Union"),
    ):
        mascara = detalle[columna]
        mapeadas = int(mascara.sum())
        energia_mapeada = detalle.loc[mascara, "Generacion_kWh"].sum()
        filas.append(
            {
                "Fuente": fuente,
                "Plantas_total": total_plantas,
                "Plantas_mapeadas": mapeadas,
                "Cobertura_plantas_pct": round(
                    100 * mapeadas / max(1, total_plantas), 2
                ),
                "Generacion_total_kWh": total_energia,
                "Generacion_mapeada_kWh": energia_mapeada,
                "Cobertura_energia_pct": round(
                    100 * energia_mapeada / total_energia
                    if total_energia
                    else 0.0,
                    4,
                ),
            }
        )
    return pd.DataFrame(filas), detalle


def _etiqueta_periodo(path: Path) -> str:
    coincidencias = re.findall(r"\d{8}", path.stem)
    return "_".join(coincidencias[-2:]) if coincidencias else date.today().strftime(
        "%Y%m%d"
    )


def actualizar_catalogo(
    base_dir: Path,
    generacion_path: Path | None = None,
    actualizar_upme: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Orquesta carga, integración, exportación y auditoría."""
    base_dir = base_dir.resolve()
    reference_dir = base_dir / "data" / "reference"
    processed_dir = base_dir / "data" / "processed"
    reference_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    simem_path = reference_dir / "dim_plantas_areas_operativas.csv"
    if not simem_path.exists():
        raise FileNotFoundError(
            "No existe dim_plantas_areas_operativas.csv. Ejecuta primero "
            "scripts/actualizar_areas_operativas_simem.py."
        )
    simem = pd.read_csv(simem_path, dtype={"Codigo_Planta": "string"})
    upme = cargar_o_actualizar_upme(base_dir, actualizar=actualizar_upme)
    catalogo = integrar_dimensiones(simem, upme)

    catalogo_path = reference_dir / "dim_plantas_operativa_geografica.csv"
    catalogo.to_csv(catalogo_path, index=False)
    print(f"Catálogo integrado: {catalogo_path} ({len(catalogo):,} plantas)")

    resumen = None
    if generacion_path and generacion_path.exists():
        generacion = pd.read_csv(
            generacion_path,
            dtype={"Codigo_Planta": "string"},
        )
        resumen, detalle = auditar_cobertura(generacion, catalogo)
        etiqueta = _etiqueta_periodo(generacion_path)
        resumen.to_csv(
            processed_dir / f"qc_cobertura_fuentes_{etiqueta}.csv",
            index=False,
        )
        detalle.to_csv(
            processed_dir / f"qc_detalle_cobertura_fuentes_{etiqueta}.csv",
            index=False,
        )
        print(resumen.to_string(index=False))
    return catalogo, resumen


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Integra la dimensión operativa SIMEM con la geografía UPME."
        )
    )
    parser.add_argument("--base-dir", type=Path, default=Path.cwd())
    parser.add_argument(
        "--generacion",
        type=Path,
        default=None,
        help="CSV opcional de generación para auditar cobertura.",
    )
    parser.add_argument(
        "--actualizar-upme",
        action="store_true",
        help="Vuelve a consultar la capa REST aunque exista caché.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    actualizar_catalogo(
        base_dir=args.base_dir,
        generacion_path=args.generacion,
        actualizar_upme=args.actualizar_upme,
    )


if __name__ == "__main__":
    main()
