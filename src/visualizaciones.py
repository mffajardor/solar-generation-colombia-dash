"""
visualizaciones.py
==================
Funciones de visualización reutilizables para el análisis de generación eléctrica.
Diseñadas para usarse tanto en notebooks como en el dashboard Streamlit (v4).

Cada función:
- Recibe el DataFrame ya procesado por etl.py
- Retorna el objeto fig de matplotlib para que el caller decida si mostrar o guardar
- Acepta un parámetro opcional `guardar_en` para exportar el PNG directamente

Uso:
    from src.visualizaciones import (
        graficar_generacion_por_tecnologia,
        graficar_perfil_horario,
        graficar_top_agentes,
        graficar_generacion_diaria,
    )
"""

import os
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN GLOBAL
# ─────────────────────────────────────────────────────────────────────────────

# Paleta de colores por tecnología — consistente en todas las figuras
COLORES_TECNOLOGIA = {
    "HIDRAULICA":  "#2196F3",  # Azul
    "SOLAR":       "#FFC107",  # Amarillo
    "TERMICA":     "#F44336",  # Rojo
    "EOLICA":      "#4CAF50",  # Verde
    "COGENERADOR": "#9E9E9E",  # Gris
}

sns.set_theme(style="whitegrid", palette="colorblind")
plt.rcParams.update({
    "figure.figsize": (12, 5),
    "axes.titlesize": 13,
    "axes.labelsize": 11,
})


def _guardar_fig(fig: plt.Figure, ruta: str) -> None:
    """Helper interno para guardar figura si se provee ruta."""
    if ruta:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        fig.savefig(ruta, dpi=150, bbox_inches="tight")
        print(f"  💾 Figura guardada en: {ruta}")


# ─────────────────────────────────────────────────────────────────────────────
# FIGURA 1 — Generación por Tecnología
# ─────────────────────────────────────────────────────────────────────────────

def graficar_generacion_por_tecnologia(
    gen_enriquecida: pd.DataFrame,
    guardar_en: str = None
) -> plt.Figure:
    """
    Dos paneles: barras de generación total (GWh) + pie de número de recursos.

    Args:
        gen_enriquecida : DataFrame procesado por construir_modelo_relacional().
        guardar_en      : Ruta opcional para exportar el PNG.

    Returns:
        Objeto Figure de matplotlib.
    """
    resumen = (
        gen_enriquecida
        .groupby("Tecnologia")
        .agg(
            Generacion_GWh=("Generacion_kWh", lambda x: x.sum() / 1e6),
            Num_Recursos=("Codigo_Planta", "nunique"),
        )
        .sort_values("Generacion_GWh", ascending=False)
        .reset_index()
    )
    resumen["Participacion_%"] = (
        resumen["Generacion_GWh"] / resumen["Generacion_GWh"].sum() * 100
    ).round(1)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Panel izquierdo — barras
    bar_colors = [COLORES_TECNOLOGIA.get(t, "#9E9E9E") for t in resumen["Tecnologia"]]
    bars = axes[0].bar(
        resumen["Tecnologia"], resumen["Generacion_GWh"],
        color=bar_colors, edgecolor="white", linewidth=0.5
    )
    for bar, pct in zip(bars, resumen["Participacion_%"]):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + resumen["Generacion_GWh"].max() * 0.01,
            f"{pct}%", ha="center", va="bottom", fontsize=9, fontweight="bold"
        )
    axes[0].set_title("Generación Total por Tecnología")
    axes[0].set_ylabel("Generación (GWh)")
    axes[0].set_xlabel("")

    # Panel derecho — pie de recursos
    pie_colors = [COLORES_TECNOLOGIA.get(t, "#9E9E9E") for t in resumen["Tecnologia"]]
    axes[1].pie(
        resumen["Num_Recursos"],
        labels=resumen["Tecnologia"],
        autopct="%1.1f%%",
        colors=pie_colors,
        startangle=140,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5}
    )
    axes[1].set_title("Número de Recursos por Tecnología")

    fig.suptitle("Parque Generador Colombiano — SIN", fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()
    _guardar_fig(fig, guardar_en)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# FIGURA 2 — Perfil Horario Solar vs Hidráulica
# ─────────────────────────────────────────────────────────────────────────────

def graficar_perfil_horario(
    gen_enriquecida: pd.DataFrame,
    tecnologias: list = None,
    guardar_en: str = None
) -> plt.Figure:
    """
    Curva de generación promedio por hora del día, normalizada al pico.
    Ideal para mostrar la complementariedad Solar-Hidráulica.

    Args:
        gen_enriquecida : DataFrame procesado por construir_modelo_relacional().
        tecnologias     : Lista de tecnologías a graficar. Default: ['SOLAR', 'HIDRAULICA'].
        guardar_en      : Ruta opcional para exportar el PNG.

    Returns:
        Objeto Figure de matplotlib.
    """
    if tecnologias is None:
        tecnologias = ["SOLAR", "HIDRAULICA"]

    fig, ax = plt.subplots(figsize=(13, 5))

    markers = ["o", "s", "^", "D"]
    for i, tec in enumerate(tecnologias):
        df_tec = gen_enriquecida[gen_enriquecida["Tecnologia"] == tec]
        if df_tec.empty:
            print(f"  ⚠️  No hay datos para tecnología: {tec}")
            continue
        perfil = df_tec.groupby("Hora")["Generacion_kWh"].mean()
        perfil_norm = perfil / perfil.max() * 100

        color = COLORES_TECNOLOGIA.get(tec, "#9E9E9E")
        ax.fill_between(perfil_norm.index, perfil_norm.values, alpha=0.15, color=color)
        ax.plot(
            perfil_norm.index, perfil_norm.values,
            color=color, lw=2.5, marker=markers[i % len(markers)], ms=5,
            label=tec.capitalize()
        )

    ax.axvspan(6, 18, alpha=0.04, color="#FFC107", label="Franja solar (6h–18h)")
    ax.set_xlim(1, 24)
    ax.set_xticks(range(1, 25))
    ax.set_xticklabels([f"{h:02d}h" for h in range(1, 25)], rotation=45, fontsize=8)
    ax.set_xlabel("Hora del día")
    ax.set_ylabel("Generación normalizada (% del pico)")
    ax.set_title("Perfil Horario Promedio por Tecnología\n(Complementariedad intra-diaria)")
    ax.legend(fontsize=10)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())

    plt.tight_layout()
    _guardar_fig(fig, guardar_en)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# FIGURA 3 — Top Agentes por Generación
# ─────────────────────────────────────────────────────────────────────────────

def graficar_top_agentes(
    gen_enriquecida: pd.DataFrame,
    top_n: int = 15,
    guardar_en: str = None
) -> plt.Figure:
    """
    Barras horizontales apiladas por tecnología para los top N agentes del mercado.

    Args:
        gen_enriquecida : DataFrame procesado por construir_modelo_relacional().
        top_n           : Número de agentes a mostrar (default: 15).
        guardar_en      : Ruta opcional para exportar el PNG.

    Returns:
        Objeto Figure de matplotlib.
    """
    gen_por_agente = (
        gen_enriquecida
        .groupby(["Codigo_Agente", "Tecnologia"])["Generacion_kWh"]
        .sum()
        .div(1e6)  # kWh → GWh
        .reset_index()
        .rename(columns={"Generacion_kWh": "Generacion_GWh"})
    )

    top_agentes = (
        gen_por_agente
        .groupby("Codigo_Agente")["Generacion_GWh"]
        .sum()
        .nlargest(top_n)
        .reset_index()
    )

    tabla_pivot = (
        gen_por_agente[gen_por_agente["Codigo_Agente"].isin(top_agentes["Codigo_Agente"])]
        .pivot_table(
            index="Codigo_Agente", columns="Tecnologia",
            values="Generacion_GWh", aggfunc="sum", fill_value=0
        )
        .reindex(top_agentes["Codigo_Agente"])
    )

    colors = [COLORES_TECNOLOGIA.get(c, "#9E9E9E") for c in tabla_pivot.columns]
    ax = tabla_pivot.plot(
        kind="barh", stacked=True, color=colors,
        figsize=(13, max(6, top_n * 0.5)),
        edgecolor="white", linewidth=0.5
    )
    ax.invert_yaxis()
    ax.set_xlabel("Generación (GWh)")
    ax.set_ylabel("Código de Agente")
    ax.set_title(f"Top {top_n} Agentes por Generación Total (por Tecnología)")
    ax.legend(title="Tecnología", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    plt.tight_layout()

    fig = ax.get_figure()
    _guardar_fig(fig, guardar_en)
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# FIGURA 4 — Generación Diaria por Tecnología
# ─────────────────────────────────────────────────────────────────────────────

def graficar_generacion_diaria(
    gen_enriquecida: pd.DataFrame,
    guardar_en: str = None
) -> plt.Figure:
    """
    Barras apiladas de generación total por día y tecnología.
    Base para la evolución de series de tiempo en v2.

    Args:
        gen_enriquecida : DataFrame procesado por construir_modelo_relacional().
        guardar_en      : Ruta opcional para exportar el PNG.

    Returns:
        Objeto Figure de matplotlib.
    """
    gen_diaria = (
        gen_enriquecida
        .groupby(["Fecha", "Tecnologia"])["Generacion_kWh"]
        .sum()
        .div(1e6)
        .reset_index()
        .rename(columns={"Generacion_kWh": "Generacion_GWh"})
    )

    tabla = gen_diaria.pivot(
        index="Fecha", columns="Tecnologia", values="Generacion_GWh"
    ).fillna(0)
    # Convertir el índice a string para evitar conflictos con matplotlib y PeriodIndex
    tabla.index = tabla.index.astype(str)

    colors = [COLORES_TECNOLOGIA.get(c, "#9E9E9E") for c in tabla.columns]
    ax = tabla.plot(
        kind="bar", stacked=True, color=colors,
        figsize=(max(10, len(tabla) * 1.2), 5),
        edgecolor="white", linewidth=0.5
    )
    ax.set_title("Generación Diaria por Tecnología")
    ax.set_xlabel("Fecha")
    ax.set_ylabel("Generación (GWh)")
    ax.set_xticklabels(
        [str(d)[:10] for d in tabla.index],
        rotation=45 if len(tabla) > 7 else 0
    )
    ax.legend(title="Tecnología", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    plt.tight_layout()

    fig = ax.get_figure()
    _guardar_fig(fig, guardar_en)
    return fig
