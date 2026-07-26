from pydantic import BaseModel
from typing import Optional
from google_antigravity import Agent

class IngestaResponse(BaseModel):
    consumo_m3: float
    alerta: bool
    tipo_alerta: Optional[str] = None
    mensaje: str

# Definición del Agente de Ingesta
agente_ingesta = Agent(
    model="gemini-2.0-flash",  # Modelo rápido y económico para imágenes/OCR
    system_instruction="""
    Eres el Agente Auditor de Lecturas de Agua para Condominios.
    Tu trabajo es:
    1. Recibir la lectura actual de un departamento y la foto del contómetro.
    2. Comparar la lectura actual contra la lectura del mes anterior.
    3. Calcular el consumo: Consumo = Lectura Actual - Lectura Anterior.
    4. Validar anomalías: Si el consumo es > 50% respecto al promedio histórico del dpto (o el mes anterior si no hay histórico), 
       marca la lectura con un flag 'ALERTA_POSIBLE_FUGA' o 'FUGA_O_ERROR'.
    5. Responder en la estructura JSON definida en response_schema.
    """,
    response_schema=IngestaResponse
)
