# Guía conceptual — por qué se combinan SIMEM y UPME

## 1. El problema

La generación XM identifica cada recurso mediante un Código SIC, pero la serie
horaria no contiene toda la información necesaria para analizar dónde se
encuentra la planta ni cómo se organiza operativamente dentro del SIN.

Una única tabla no resuelve ambos conceptos:

- la **estructura operativa** describe la organización del sistema;
- la **ubicación geográfica** describe dónde está físicamente el recurso.

## 2. Dimensión operativa SIMEM

SIMEM relaciona la planta con un código de área y subárea operativa. Esta fuente
permite responder preguntas como:

- ¿cuánta generación se reportó en cada área operativa?;
- ¿qué tecnologías participan en una subárea?;
- ¿cómo cambia el perfil horario entre ámbitos operativos?

Una planta sin correspondencia SIMEM se conserva como `Sin asignar`. No se
deduce su área a partir del departamento.

## 3. Dimensión geográfica UPME

El geovisor UPME consume una capa ArcGIS que publica proyectos de generación
provenientes de XM. La capa incluye Código SIC, departamento, municipio,
código DANE, coordenadas, capacidad, tecnología, clasificación y estado.

Esta fuente permite responder:

- ¿en qué departamentos se concentra la generación?;
- ¿qué perfil presentan Caribe, Antioquia o el centro del país?;
- ¿dónde están los recursos solares no encontrados en SIMEM?;
- ¿qué plantas pueden representarse posteriormente en un mapa?

## 4. El cruce

La llave común es:

```text
Codigo_Planta XM/SIMEM ↔ codigo_sic UPME
```

El cruce es externo para construir el catálogo maestro y posteriormente
izquierdo desde la generación. Así se evita eliminar energía cuando una fuente
no contiene determinado código.

## 5. Cómo interpretar la cobertura

La cobertura por plantas cuenta cuántos códigos distintos tienen
correspondencia. La cobertura por energía pondera esos códigos por la energía
del período.

Por eso SIMEM puede cubrir 79,84 % de las plantas y, al mismo tiempo, 97,5721 %
de la energía: los recursos sin correspondencia son numerosos, pero
individualmente pequeños, principalmente solares no despachados centralmente.

UPME alcanza 98,81 % de las plantas y 99,9863 % de la energía. La unión identifica
las 506 plantas del período, pero esto no significa que todas tengan área
operativa: significa que todas aparecen al menos en uno de los dos catálogos.

## 6. Precauciones

1. No usar departamento como sustituto del área operativa.
2. No eliminar `Sin asignar` de los totales nacionales.
3. Conservar fecha y fuente de cada dimensión.
4. Mantener los valores numéricos sin el redondeo visual del geovisor.
5. Convertir las fechas ArcGIS a la zona horaria de Colombia antes de obtener
   la fecha civil.
6. Revisar periódicamente cambios de esquema o disponibilidad de la capa REST.

## 7. Escalabilidad

El catálogo integrado deja preparado el proyecto para:

- mapas interactivos;
- análisis solar por municipio o región;
- comparación entre distribución geográfica y operación del SIN;
- filtros territoriales en Streamlit;
- controles de calidad automáticos cuando aparezcan nuevas plantas.
