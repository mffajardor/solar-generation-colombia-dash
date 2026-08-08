"""Descarga y prepara el mapa planta -> area/subarea operativa de SIMEM.

Fuentes oficiales:
    0bfc9d : Parametros tecnicos de las plantas de generacion.
    841808 : Listado de areas operativas del SIN.
    10F2C9 : Listado de subareas operativas del SIN.

El script conserva las respuestas originales en data/raw/simem y exporta una
dimension lista para cruzar con Gene en:

    data/reference/dim_plantas_areas_operativas.csv
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


API_DATOS = "https://www.simem.co/backend-files/api/datos-publicos"

DATASETS = {
    "plantas": "0bfc9d",
    "areas": "841808",
    "subareas": "10F2C9",
}


@dataclass(frozen=True)
class DescargaSIMEM:
    dataset_id: str
    fecha_solicitada: date
    fecha_datos: date | None
    datos: pd.DataFrame
    origen: str


def crear_sesion() -> requests.Session:
    """Crea una sesion con reintentos para errores transitorios."""
    reintentos = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
    )
    sesion = requests.Session()
    sesion.mount("https://", HTTPAdapter(max_retries=reintentos))
    sesion.headers.update({"User-Agent": "solar-generation-colombia-dash/2.2"})
    return sesion


def _extraer_registros(payload: Any) -> list[dict[str, Any]]:
    """Normaliza las dos formas de respuesta observadas en SIMEM."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        resultado = payload.get("result", payload)
        if isinstance(resultado, dict):
            registros = resultado.get("records", [])
            return registros if isinstance(registros, list) else []
    return []


def _fecha_maxima(datos: pd.DataFrame) -> date | None:
    if "Fecha" not in datos.columns or datos.empty:
        return None
    fechas = pd.to_datetime(datos["Fecha"], errors="coerce").dropna()
    return fechas.max().date() if not fechas.empty else None


def _rutas_cache(cache_dir: Path, dataset_id: str, fecha: date) -> tuple[Path, Path]:
    base = cache_dir / f"simem_{dataset_id.lower()}_{fecha:%Y%m%d}"
    return base.with_suffix(".json"), base.with_suffix(".csv")


def _leer_cache_mas_reciente(
    cache_dir: Path,
    dataset_id: str,
) -> DescargaSIMEM | None:
    candidatos = sorted(
        cache_dir.glob(f"simem_{dataset_id.lower()}_*.csv"),
        reverse=True,
    )
    for ruta in candidatos:
        try:
            datos = pd.read_csv(ruta, dtype={"CodigoPlanta": "string"})
            fecha_texto = ruta.stem.rsplit("_", 1)[-1]
            fecha_solicitada = datetime.strptime(fecha_texto, "%Y%m%d").date()
            if not datos.empty:
                return DescargaSIMEM(
                    dataset_id=dataset_id,
                    fecha_solicitada=fecha_solicitada,
                    fecha_datos=_fecha_maxima(datos),
                    datos=datos,
                    origen=f"cache:{ruta.name}",
                )
        except (OSError, ValueError, pd.errors.ParserError):
            continue
    return None


def descargar_ultimo_disponible(
    dataset_id: str,
    cache_dir: Path,
    fecha_referencia: date | None = None,
    dias_retroceso: int = 7,
    actualizar_api: bool = False,
    timeout: int = 120,
    sesion: requests.Session | None = None,
) -> DescargaSIMEM:
    """Descarga el ultimo dia disponible o reutiliza el cache local."""
    cache_dir.mkdir(parents=True, exist_ok=True)

    if not actualizar_api:
        cache = _leer_cache_mas_reciente(cache_dir, dataset_id)
        if cache is not None:
            return cache

    fecha_referencia = fecha_referencia or date.today()
    sesion = sesion or crear_sesion()
    ultimo_error: Exception | None = None

    for desplazamiento in range(dias_retroceso + 1):
        fecha_consulta = fecha_referencia - timedelta(days=desplazamiento)
        parametros = {
            "datasetId": dataset_id,
            "startDate": fecha_consulta.isoformat(),
            "endDate": fecha_consulta.isoformat(),
        }
        try:
            respuesta = sesion.post(API_DATOS, params=parametros, timeout=timeout)
            respuesta.raise_for_status()
            payload = respuesta.json()
            registros = _extraer_registros(payload)
            if not registros:
                continue

            datos = pd.DataFrame.from_records(registros)
            ruta_json, ruta_csv = _rutas_cache(cache_dir, dataset_id, fecha_consulta)
            ruta_json.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            datos.to_csv(ruta_csv, index=False)
            return DescargaSIMEM(
                dataset_id=dataset_id,
                fecha_solicitada=fecha_consulta,
                fecha_datos=_fecha_maxima(datos),
                datos=datos,
                origen=f"api:{respuesta.url}",
            )
        except (requests.RequestException, ValueError) as exc:
            ultimo_error = exc

    cache = _leer_cache_mas_reciente(cache_dir, dataset_id)
    if cache is not None:
        print(
            f"Advertencia: no fue posible actualizar {dataset_id}; "
            f"se reutiliza {cache.origen}."
        )
        return cache

    detalle = f" Ultimo error: {ultimo_error}" if ultimo_error else ""
    raise RuntimeError(
        f"SIMEM no devolvio datos para {dataset_id} en los ultimos "
        f"{dias_retroceso + 1} dias.{detalle}"
    )


def _validar_columnas(datos: pd.DataFrame, requeridas: set[str], nombre: str) -> None:
    faltantes = requeridas.difference(datos.columns)
    if faltantes:
        raise ValueError(f"{nombre}: faltan columnas obligatorias {sorted(faltantes)}")


def construir_dimension_operativa(
    plantas: pd.DataFrame,
    areas: pd.DataFrame,
    subareas: pd.DataFrame,
) -> pd.DataFrame:
    """Relaciona las plantas con los nombres oficiales de area y subarea."""
    _validar_columnas(
        plantas,
        {
            "CodigoPlanta",
            "NombrePlanta",
            "CodigoAreaOperativa",
            "CodigoSubAreaOperativa",
        },
        "plantas",
    )
    _validar_columnas(
        areas,
        {"CodigoAreaOperativa", "NombreAreaOperativa"},
        "areas",
    )
    _validar_columnas(
        subareas,
        {"CodigoSubAreaOperativa", "NombreSubareaOperativa"},
        "subareas",
    )

    columnas_plantas = [
        "CodigoPlanta",
        "NombrePlanta",
        "CodigoAreaOperativa",
        "CodigoSubAreaOperativa",
        "TipoGeneracion",
        "TipoDespachoRecurso",
        "CodigoSICAgente",
        "Fecha",
        "FechaPublicacion",
    ]
    columnas_plantas = [c for c in columnas_plantas if c in plantas.columns]
    base = plantas[columnas_plantas].copy()
    base["CodigoPlanta"] = base["CodigoPlanta"].astype("string").str.strip()
    base = base.dropna(subset=["CodigoPlanta"])

    # Ante una respuesta con varias filas por planta se conserva la mas reciente.
    columnas_fecha = [c for c in ("Fecha", "FechaPublicacion") if c in base.columns]
    for columna in columnas_fecha:
        base[columna] = pd.to_datetime(base[columna], errors="coerce")
    if columnas_fecha:
        base = base.sort_values(columnas_fecha)
    base = base.drop_duplicates("CodigoPlanta", keep="last")

    areas_dim = (
        areas[["CodigoAreaOperativa", "NombreAreaOperativa"]]
        .dropna(subset=["CodigoAreaOperativa"])
        .drop_duplicates("CodigoAreaOperativa", keep="last")
    )
    subareas_dim = (
        subareas[["CodigoSubAreaOperativa", "NombreSubareaOperativa"]]
        .dropna(subset=["CodigoSubAreaOperativa"])
        .drop_duplicates("CodigoSubAreaOperativa", keep="last")
    )

    dimension = (
        base.merge(
            areas_dim,
            on="CodigoAreaOperativa",
            how="left",
            validate="many_to_one",
        )
        .merge(
            subareas_dim,
            on="CodigoSubAreaOperativa",
            how="left",
            validate="many_to_one",
        )
        .rename(
            columns={
                "CodigoPlanta": "Codigo_Planta",
                "NombrePlanta": "Nombre_Planta_SIMEM",
                "NombreAreaOperativa": "Area_Operativa",
                "NombreSubareaOperativa": "Subarea_Operativa",
            }
        )
    )

    dimension["Area_Operativa"] = dimension["Area_Operativa"].fillna("Sin asignar")
    dimension["Subarea_Operativa"] = dimension["Subarea_Operativa"].fillna(
        "Sin asignar"
    )
    dimension["Fuente"] = "SIMEM 0bfc9d + 841808 + 10F2C9"

    orden = [
        "Codigo_Planta",
        "Nombre_Planta_SIMEM",
        "CodigoAreaOperativa",
        "Area_Operativa",
        "CodigoSubAreaOperativa",
        "Subarea_Operativa",
        "TipoGeneracion",
        "TipoDespachoRecurso",
        "CodigoSICAgente",
        "Fecha",
        "FechaPublicacion",
        "Fuente",
    ]
    return dimension[[c for c in orden if c in dimension.columns]].sort_values(
        ["Area_Operativa", "Subarea_Operativa", "Nombre_Planta_SIMEM"]
    )


def calcular_cobertura(
    generacion: pd.DataFrame,
    dimension: pd.DataFrame,
) -> dict[str, float | int]:
    """Calcula cobertura por plantas y por energia sin excluir registros."""
    _validar_columnas(generacion, {"Codigo_Planta"}, "generacion")
    codigos_mapa = set(dimension["Codigo_Planta"].dropna().astype(str))
    codigos_generacion = set(generacion["Codigo_Planta"].dropna().astype(str))
    coinciden = codigos_generacion.intersection(codigos_mapa)

    resultado: dict[str, float | int] = {
        "plantas_generacion": len(codigos_generacion),
        "plantas_mapeadas": len(coinciden),
        "cobertura_plantas_pct": round(
            100 * len(coinciden) / max(1, len(codigos_generacion)), 2
        ),
    }

    if "Generacion_kWh" in generacion.columns:
        energia = pd.to_numeric(generacion["Generacion_kWh"], errors="coerce")
        total = float(energia.sum())
        mapeada = float(
            energia[generacion["Codigo_Planta"].astype(str).isin(coinciden)].sum()
        )
        resultado["cobertura_energia_pct"] = round(
            100 * mapeada / total if total else 0.0,
            4,
        )
    return resultado


def actualizar_dimension(
    base_dir: Path,
    fecha_referencia: date | None = None,
    dias_retroceso: int = 7,
    actualizar_api: bool = False,
    generacion_path: Path | None = None,
) -> tuple[pd.DataFrame, dict[str, float | int] | None]:
    """Orquesta descarga, validacion y exportacion de la dimension."""
    base_dir = base_dir.resolve()
    cache_dir = base_dir / "data" / "raw" / "simem"
    reference_dir = base_dir / "data" / "reference"
    salida = reference_dir / "dim_plantas_areas_operativas.csv"
    reference_dir.mkdir(parents=True, exist_ok=True)

    if salida.exists() and not actualizar_api:
        dimension = pd.read_csv(salida, dtype={"Codigo_Planta": "string"})
        print(f"Se reutiliza la dimension existente: {salida}")
    else:
        sesion = crear_sesion()
        descargas = {
            nombre: descargar_ultimo_disponible(
                dataset_id,
                cache_dir=cache_dir,
                fecha_referencia=fecha_referencia,
                dias_retroceso=dias_retroceso,
                actualizar_api=actualizar_api,
                sesion=sesion,
            )
            for nombre, dataset_id in DATASETS.items()
        }
        dimension = construir_dimension_operativa(
            descargas["plantas"].datos,
            descargas["areas"].datos,
            descargas["subareas"].datos,
        )
        dimension.to_csv(salida, index=False)
        print(f"Dimension exportada: {salida}")
        for nombre, descarga in descargas.items():
            print(
                f"  {nombre}: {len(descarga.datos):,} filas | "
                f"fecha datos: {descarga.fecha_datos} | {descarga.origen}"
            )

    cobertura = None
    if generacion_path and generacion_path.exists():
        generacion = pd.read_csv(
            generacion_path,
            dtype={"Codigo_Planta": "string"},
        )
        cobertura = calcular_cobertura(generacion, dimension)
        print("Cobertura:", json.dumps(cobertura, ensure_ascii=False))

    return dimension, cobertura


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Actualiza la dimension de areas operativas desde SIMEM."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Raiz del proyecto que contiene data/.",
    )
    parser.add_argument(
        "--fecha",
        type=date.fromisoformat,
        default=None,
        help="Fecha de referencia YYYY-MM-DD; por defecto usa hoy.",
    )
    parser.add_argument(
        "--dias-retroceso",
        type=int,
        default=7,
        help="Dias anteriores que se prueban si no hay datos.",
    )
    parser.add_argument(
        "--actualizar",
        action="store_true",
        help="Ignora la dimension/cache existente y vuelve a consultar SIMEM.",
    )
    parser.add_argument(
        "--generacion",
        type=Path,
        default=None,
        help="CSV opcional para calcular cobertura del mapeo.",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    actualizar_dimension(
        base_dir=args.base_dir,
        fecha_referencia=args.fecha,
        dias_retroceso=max(0, args.dias_retroceso),
        actualizar_api=args.actualizar,
        generacion_path=args.generacion,
    )


if __name__ == "__main__":
    main()
