import inspect
import os
import sys
import traceback
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from agentes.ingesta import agente_ingesta
from agentes.prorrateo import agente_prorrateo
from agentes.reportes import agente_reportes
from tools.supabase_client import (
    guardar_lectura,
    guardar_liquidacion,
    guardar_recibos_generados,
    supabase,
)

app = FastAPI(title="Cerebro de Agua para Condominios")


async def deserializar_salida(st_out):
  """Estructura de forma segura objetos de respuesta Pydantic o SDK sin forzar corrutinas."""
  if st_out is None:
    return {}

  # Evaluamos si es una función
  if callable(st_out) and not inspect.isclass(st_out):
    st_out = st_out()

  # Evaluamos si es un objeto awaitable explícito
  if inspect.isawaitable(st_out):
    st_out = await st_out

  # Extracción segura según tipo de objeto Pydantic / dict
  if hasattr(st_out, "model_dump"):
    return st_out.model_dump()
  elif hasattr(st_out, "dict"):
    return st_out.dict()
  elif isinstance(st_out, dict):
    return st_out

  return {"raw": str(st_out)}


@app.post("/api/validar-lectura")
async def validar_y_guardar_lectura(
    departamento_id: str = Form(...),
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    foto: UploadFile = File(None),
):
  try:
    foto_url = None
    if foto and supabase:
      file_bytes = await foto.read()
      file_path = f"medidores/{departamento_id}_{foto.filename}"
      try:
        supabase.storage.from_("evidencias-contometros").upload(
            file_path, file_bytes
        )
        foto_url = supabase.storage.from_("evidencias-contometros").get_public_url(
            file_path
        )
      except Exception as e:
        print(f"Warning upload: {e}")

    respuesta = await agente_ingesta.run(
        prompt=(
            f"Departamento: {departamento_id}\nLectura Anterior:"
            f" {lectura_anterior}\nLectura Actual: {lectura_actual}"
        ),
        attachments=[foto] if foto else [],
    )

    st_out = getattr(respuesta, "structured_output", respuesta)
    resultado_dict = await deserializar_salida(st_out)

    try:
      await guardar_lectura(
          departamento=departamento_id,
          lectura_m3=lectura_actual,
          foto_url=foto_url,
          incidencia=resultado_dict.get("mensaje"),
      )
    except Exception as e:
      print(f"Error Supabase: {e}")

    return resultado_dict

  except Exception as err:
    return {
        "status": "error",
        "message": str(err),
        "traceback": traceback.format_exc(),
    }


@app.post("/api/liquidar-mes")
async def liquidar_y_guardar_mes(datos: dict):
  try:
    respuesta = await agente_prorrateo.run(
        prompt=f"Procesa la liquidación con la siguiente información: {datos}"
    )

    st_out = getattr(respuesta, "structured_output", respuesta)
    liquidacion_dict = await deserializar_salida(st_out)

    try:
      db_record = {
          "condominio_id": liquidacion_dict.get("condominio_id", ""),
          "periodo": liquidacion_dict.get("periodo", ""),
          "total_medidor_general_m3": liquidacion_dict.get(
              "total_medidor_general_m3", 0
          ),
          "total_suma_departamentos_m3": liquidacion_dict.get(
              "total_suma_departamentos_m3", 0
          ),
          "consumo_areas_comunes_m3": liquidacion_dict.get(
              "consumo_areas_comunes_m3", 0
          ),
          "monto_total_factura": liquidacion_dict.get(
              "monto_total_factura_agua", 0
          ),
          "costo_por_m3": liquidacion_dict.get("costo_por_m3", 0),
          "desglose_json": liquidacion_dict,
      }
      await guardar_liquidacion(db_record)
    except Exception as e:
      print(f"Error Supabase liquidacion: {e}")

    return liquidacion_dict

  except Exception as err:
    return {
        "status": "error",
        "message": str(err),
        "traceback": traceback.format_exc(),
    }