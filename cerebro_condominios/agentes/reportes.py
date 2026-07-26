from pydantic import BaseModel
from typing import List, Optional
from google_antigravity import Agent

class ReciboDepartamentoHTML(BaseModel):
    departamento_id: str
    periodo: str
    monto_a_pagar: float
    html_code: str
    resumen_whatsapp: str
    resumen_texto_whatsapp: str

class ReporteMensualResponse(BaseModel):
    condominio_id: str
    periodo: str
    recibos: List[ReciboDepartamentoHTML]

# Definición del Agente de Reportes
agente_reportes = Agent(
    model="gemini-2.0-flash",
    response_schema=ReporteMensualResponse,
    system_instruction="""
    Eres el Agente Diseñador de Recibos y Comunicaciones para Condominios.
    
    Tu trabajo es:
    1. Recibir los datos consolidados de la liquidación del mes.
    2. Generar para cada departamento una plantilla HTML estilizada, limpia y profesional (listo para convertir a PDF) que incluya:
       - Encabezado con Nombre del Condominio, Departamento y Periodo.
       - Cuadro con Lectura Anterior, Lectura Actual y Consumo en m³.
       - Fotografía de la evidencia del medidor (vía URL).
       - Desglose financiero: Consumo propio + Cuota de áreas comunes = Total a Pagar.
       - Si existe una alerta de fuga, incluir una sección destacada en rojo advirtiendo al propietario.
    3. Generar un mensaje corto en texto plano optimizado para enviarse por WhatsApp a cada residente (campos 'resumen_whatsapp' y 'resumen_texto_whatsapp' con el mismo texto).
    """
)
