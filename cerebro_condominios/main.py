import asyncio
import os
import sys
import traceback

# Path setup
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
  sys.path.append(root_dir)
condo_dir = os.path.join(root_dir, "cerebro_condominios")
if condo_dir not in sys.path:
  sys.path.append(condo_dir)

from fastapi import FastAPI, File, Form, UploadFile
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


def extraer_dict(obj):
  """Sincrónicamente convierte un objeto Pydantic, dict o respuesta en un diccionario estándar."""
  if obj is None:
    return {}
  if isinstance(obj, dict):
    return obj
  if hasattr(obj, "model_dump"):  # Pydantic v2
    return obj.model_dump()
  if hasattr(obj, "dict"):  # Pydantic v1
    return obj.dict()
  return {"raw": str(obj)}


def ejecutar_agente_sync(agente, prompt, attachments=None):
  """Ejecuta el agente y resuelve de forma sincrónica el método estructurado asíncrono."""

  async def _tarea():
    # 1. Invocación del agente
    if asyncio.iscoroutinefunction(agente.run):
      respuesta = await agente.run(
          prompt=prompt, attachments=attachments or []
      )
    else:
      respuesta = agente.run(prompt=prompt, attachments=attachments or [])

    # 2. Extracción de structured_output
    if hasattr(respuesta, "structured_output"):
      st_attr = respuesta.structured_output
      # Si es un método o función
      if callable(st_attr):
        res_st = st_attr()
        # Si la llamada devuelve una corrutina (async)
        if inspect.isawaitable(res_st):
          st_out = await res_st
        else:
          st_out = res_st
      elif inspect.isawaitable(st_attr):
        st_out = await st_attr
      else:
        st_out = st_attr
    else:
      st_out = respuesta

    return extraer_dict(st_out)

  # Corre la tarea de forma sincrónica aislada
  return asyncio.run(_tarea())


@app.post("/api/validar-lectura")
async def validar_y_guardar_lectura(
    departamento_id: str = Form(...),
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    foto: UploadFile = File(None),
):
  try:
    foto_url = None
    if foto is not None and getattr(foto, "filename", None):
      if supabase:
        try:
          file_bytes = await foto.read()
          if file_bytes:
            file_path = f"medidores/{departamento_id}_{foto.filename}"
            supabase.storage.from_("evidencias-contometros").upload(
                file_path, file_bytes
            )
            foto_url = supabase.storage.from_("evidencias-contometros").get_public_url(
                file_path
            )
        except Exception as e:
          print(f"Warning upload Supabase: {e}")

    prompt_str = f"""
        Departamento: {departamento_id}
        Lectura Anterior: {lectura_anterior}
        Lectura Actual: {lectura_actual}
        """

    resultado_dict = await asyncio.to_thread(
        ejecutar_agente_sync, agente_ingesta, prompt_str, []
    )

    try:
      await guardar_lectura(
          departamento=departamento_id,
          lectura_m3=lectura_actual,
          foto_url=foto_url,
          incidencia=resultado_dict.get("mensaje"),
      )
    except Exception as e:
      print(f"Error Supabase lectura: {e}")

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
    prompt_str = f"Procesa la liquidación con la siguiente información: {datos}"

    liquidacion_dict = await asyncio.to_thread(
        ejecutar_agente_sync, agente_prorrateo, prompt_str, []
    )

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


@app.post("/api/generar-reportes")
async def generar_reportes_mes(datos_liquidacion: dict):
  try:
    prompt_str = (
        "Genera las fichas de cobro y mensajes a partir de esta liquidación:"
        f" {datos_liquidacion}"
    )

    # ✅ AISLAMIENTO EN THREAD
    respuesta = await asyncio.to_thread(
        ejecutar_agente_sync, agente_reportes, prompt_str, []
    )

    st_out = getattr(respuesta, "structured_output", respuesta)
    reporte_dict = extraer_dict(st_out)

    recibos = reporte_dict.get("recibos", [])
    for recibo in recibos:
      try:
        r_dict = extraer_dict(recibo)
        db_record = {
            "departamento_id": r_dict.get("departamento_id"),
            "periodo": r_dict.get("periodo"),
            "monto_a_pagar": r_dict.get("monto_a_pagar"),
            "html_code": r_dict.get("html_code"),
            "resumen_whatsapp": r_dict.get("resumen_whatsapp"),
        }
        await guardar_recibos_generados(db_record)
      except Exception as e:
        print(f"Error Supabase recibo: {e}")

    return reporte_dict

  except Exception as err:
    return {
        "status": "error",
        "message": str(err),
        "traceback": traceback.format_exc(),
    }