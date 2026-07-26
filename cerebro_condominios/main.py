import os
import sys
import inspect

# Ensure both project root and cerebro_condominios are in the path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)
condo_dir = os.path.join(root_dir, "cerebro_condominios")
if condo_dir not in sys.path:
    sys.path.append(condo_dir)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from agentes.ingesta import agente_ingesta, IngestaResponse
from agentes.prorrateo import agente_prorrateo, LiquidacionResponse
from agentes.reportes import agente_reportes, ReporteMensualResponse
from tools.supabase_client import supabase, guardar_lectura, guardar_liquidacion, guardar_recibos_generados

app = FastAPI(title="Cerebro de Agua para Condominios")


async def _resolver_salida(respuesta_agente):
    """Auxiliar para resolver de forma segura si es corrutina, método o propiedad directas."""
    st_out = respuesta_agente.structured_output
    if callable(st_out):
        st_out = st_out()
    if inspect.isawaitable(st_out):
        st_out = await st_out
    return st_out


@app.post("/api/validar-lectura", response_model=IngestaResponse)
async def validar_y_guardar_lectura(
    departamento_id: str = Form(...),
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    foto: UploadFile = File(None)
):
    foto_url = None
    if foto:
        if not supabase:
            print("Warning: Supabase client not initialized. Cannot upload photo.")
        else:
            file_bytes = await foto.read()
            file_path = f"medidores/{departamento_id}_{foto.filename}"
            try:
                supabase.storage.from_("evidencias-contometros").upload(file_path, file_bytes)
                foto_url = supabase.storage.from_("evidencias-contometros").get_public_url(file_path)
            except Exception as e:
                print(f"Warning: Failed to upload file to Supabase storage: {e}")

    respuesta = await agente_ingesta.run(
        prompt=f"""
        Departamento: {departamento_id}
        Lectura Anterior: {lectura_anterior}
        Lectura Actual: {lectura_actual}
        """,
        attachments=[foto] if foto else []
    )
    
    st_out = await _resolver_salida(respuesta)
    resultado_json = st_out.dict() if hasattr(st_out, 'dict') else st_out

    await guardar_lectura(
        departamento=departamento_id,
        lectura_m3=lectura_actual,
        foto_url=foto_url,
        incidencia=resultado_json.get("mensaje") if isinstance(resultado_json, dict) else getattr(resultado_json, 'mensaje', None)
    )

    return st_out


@app.post("/api/liquidar-mes", response_model=LiquidacionResponse)
async def liquidar_y_guardar_mes(datos: dict):
    respuesta = await agente_prorrateo.run(
        prompt=f"Procesa la liquidación con la siguiente información: {datos}"
    )
    
    st_out = await _resolver_salida(respuesta)
    liquidacion_dict = st_out.dict() if hasattr(st_out, 'dict') else st_out

    db_record = {
        "condominio_id": liquidacion_dict["condominio_id"],
        "periodo": liquidacion_dict["periodo"],
        "total_medidor_general_m3": liquidacion_dict["total_medidor_general_m3"],
        "total_suma_departamentos_m3": liquidacion_dict["total_suma_departamentos_m3"],
        "consumo_areas_comunes_m3": liquidacion_dict["consumo_areas_comunes_m3"],
        "monto_total_factura": liquidacion_dict["monto_total_factura_agua"],
        "costo_por_m3": liquidacion_dict["costo_por_m3"],
        "desglose_json": liquidacion_dict
    }
    await guardar_liquidacion(db_record)

    return st_out


@app.post("/api/generar-reportes", response_model=ReporteMensualResponse)
async def generar_reportes_mes(datos_liquidacion: dict):
    respuesta = await agente_reportes.run(
        prompt=f"Genera las fichas de cobro y mensajes a partir de esta liquidación: {datos_liquidacion}"
    )
    
    st_out = await _resolver_salida(respuesta)
    reporte_dict = st_out.dict() if hasattr(st_out, 'dict') else st_out

    recibos = reporte_dict.get("recibos", []) if isinstance(reporte_dict, dict) else getattr(reporte_dict, 'recibos', [])
    for recibo in recibos:
        r_dict = recibo.dict() if hasattr(recibo, 'dict') else recibo
        db_record = {
            "departamento_id": r_dict["departamento_id"],
            "periodo": r_dict["periodo"],
            "monto_a_pagar": r_dict["monto_a_pagar"],
            "html_code": r_dict["html_code"],
            "resumen_whatsapp": r_dict["resumen_whatsapp"]
        }
        await guardar_recibos_generados(db_record)

    return st_out