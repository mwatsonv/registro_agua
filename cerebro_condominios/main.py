import os
import sys
import traceback

# Configurar paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
condo_dir = os.path.join(root_dir, "cerebro_condominios")
if condo_dir not in sys.path:
    sys.path.append(condo_dir)

from fastapi import FastAPI, UploadFile, File, Form
from agentes.ingesta import agente_ingesta
from agentes.prorrateo import agente_prorrateo
from agentes.reportes import agente_reportes
from tools.supabase_client import supabase, guardar_lectura, guardar_liquidacion, guardar_recibos_generados

app = FastAPI(title="Cerebro de Agua para Condominios")


def extraer_dict(obj):
    """Sincrónicamente convierte un objeto Pydantic o dict en un diccionario estándar."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):  # Pydantic v2
        return obj.model_dump()
    if hasattr(obj, "dict"):        # Pydantic v1
        return obj.dict()
    return {"raw": str(obj)}


@app.post("/api/validar-lectura")
async def validar_y_guardar_lectura(
    departamento_id: str = Form(...),
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    foto: UploadFile = File(None)
):
    try:
        foto_url = None
        if foto and supabase:
            file_bytes = await foto.read()
            file_path = f"medidores/{departamento_id}_{foto.filename}"
            try:
                supabase.storage.from_("evidencias-contometros").upload(file_path, file_bytes)
                foto_url = supabase.storage.from_("evidencias-contometros").get_public_url(file_path)
            except Exception as e:
                print(f"Warning upload Supabase: {e}")

        # Invocación directa del agente
        respuesta = await agente_ingesta.run(
            prompt=f"""
            Departamento: {departamento_id}
            Lectura Anterior: {lectura_anterior}
            Lectura Actual: {lectura_actual}
            """,
            attachments=[foto] if foto else []
        )

        # Extraer el resultado estructurado
        st_out = getattr(respuesta, "structured_output", respuesta)
        resultado_dict = extraer_dict(st_out)

        try:
            await guardar_lectura(
                departamento=departamento_id,
                lectura_m3=lectura_actual,
                foto_url=foto_url,
                incidencia=resultado_dict.get("mensaje")
            )
        except Exception as e:
            print(f"Error Supabase lectura: {e}")

        return resultado_dict

    except Exception as err:
        return {
            "status": "error",
            "message": str(err),
            "traceback": traceback.format_exc()
        }


@app.post("/api/liquidar-mes")
async def liquidar_y_guardar_mes(datos: dict):
    try:
        respuesta = await agente_prorrateo.run(
            prompt=f"Procesa la liquidación con la siguiente información: {datos}"
        )

        st_out = getattr(respuesta, "structured_output", respuesta)
        liquidacion_dict = extraer_dict(st_out)

        try:
            db_record = {
                "condominio_id": liquidacion_dict.get("condominio_id", ""),
                "periodo": liquidacion_dict.get("periodo", ""),
                "total_medidor_general_m3": liquidacion_dict.get("total_medidor_general_m3", 0),
                "total_suma_departamentos_m3": liquidacion_dict.get("total_suma_departamentos_m3", 0),
                "consumo_areas_comunes_m3": liquidacion_dict.get("consumo_areas_comunes_m3", 0),
                "monto_total_factura": liquidacion_dict.get("monto_total_factura_agua", 0),
                "costo_por_m3": liquidacion_dict.get("costo_por_m3", 0),
                "desglose_json": liquidacion_dict
            }
            await guardar_liquidacion(db_record)
        except Exception as e:
            print(f"Error Supabase liquidacion: {e}")

        return liquidacion_dict

    except Exception as err:
        return {
            "status": "error",
            "message": str(err),
            "traceback": traceback.format_exc()
        }


@app.post("/api/generar-reportes")
async def generar_reportes_mes(datos_liquidacion: dict):
    try:
        respuesta = await agente_reportes.run(
            prompt=f"Genera las fichas de cobro y mensajes a partir de esta liquidación: {datos_liquidacion}"
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
                    "resumen_whatsapp": r_dict.get("resumen_whatsapp")
                }
                await guardar_recibos_generados(db_record)
            except Exception as e:
                print(f"Error Supabase recibo: {e}")

        return reporte_dict

    except Exception as err:
        return {
            "status": "error",
            "message": str(err),
            "traceback": traceback.format_exc()
        }