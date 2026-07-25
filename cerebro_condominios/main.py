import os
import sys

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

@app.post("/api/validar-lectura", response_model=IngestaResponse)
async def validar_y_guardar_lectura(
    departamento_id: str = Form(...),
    lectura_anterior: float = Form(...),
    lectura_actual: float = Form(...),
    foto: UploadFile = File(None)
):
    # 1. Subir la foto de evidencia al bucket de Supabase si existe y el cliente está configurado
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
                # We catch storage exceptions in case the bucket doesn't exist or credentials fail
                print(f"Warning: Failed to upload file to Supabase storage: {e}")

    # 2. Ejecutar el Agente de Ingesta en Antigravity
    respuesta = await agente_ingesta.run(
        prompt=f"""
        Departamento: {departamento_id}
        Lectura Anterior: {lectura_anterior}
        Lectura Actual: {lectura_actual}
        """,
        attachments=[foto] if foto else []
    )
    resultado_json = respuesta.structured_output.dict()

    # 3. Guardar en Base de Datos
    await guardar_lectura(
        departamento_id=departamento_id,
        respuesta_agente={**resultado_json, "lectura_anterior": lectura_anterior, "lectura_actual": lectura_actual},
        foto_url=foto_url
    )

    return respuesta.structured_output

@app.post("/api/liquidar-mes", response_model=LiquidacionResponse)
async def liquidar_y_guardar_mes(datos: dict):
    # 1. Ejecutar el Agente de Prorrateo
    respuesta = await agente_prorrateo.run(
        prompt=f"Procesa la liquidación con la siguiente información: {datos}"
    )
    liquidacion_dict = respuesta.structured_output.dict()

    # 2. Persistir el resumen financiero
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

    return respuesta.structured_output

@app.post("/api/generar-reportes", response_model=ReporteMensualResponse)
async def generar_reportes_mes(datos_liquidacion: dict):
    """
    Genera las plantillas HTML (PDFs) y los mensajes de WhatsApp
    para cada departamento basándose en la liquidación procesada.
    """
    respuesta = await agente_reportes.run(
        prompt=f"Genera las fichas de cobro y mensajes a partir de esta liquidación: {datos_liquidacion}"
    )
    reporte_dict = respuesta.structured_output.dict()

    # Guardar cada recibo generado en la base de datos
    for recibo in reporte_dict.get("recibos", []):
        db_record = {
            "departamento_id": recibo["departamento_id"],
            "periodo": recibo["periodo"],
            "monto_a_pagar": recibo["monto_a_pagar"],
            "html_code": recibo["html_code"],
            "resumen_whatsapp": recibo["resumen_whatsapp"]
        }
        await guardar_recibos_generados(db_record)

    return respuesta.structured_output
