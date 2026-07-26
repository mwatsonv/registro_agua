from typing import List, Optional
from google_antigravity import Agent
from pydantic import BaseModel


class DetalleDepartamento(BaseModel):
  departamento_id: str
  consumo_propio_m3: float
  cuota_areas_comunes_m3: float
  total_consumo_m3: float
  monto_a_pagar: float


class LiquidacionResponse(BaseModel):
  condominio_id: str
  periodo: str
  total_medidor_general_m3: float
  total_suma_departamentos_m3: float
  consumo_areas_comunes_m3: float
  monto_total_factura_agua: float
  costo_por_m3: float
  desglose_departamentos: List[DetalleDepartamento]
  observaciones: Optional[str] = None


def crear_agente_prorrateo() -> Agent:
  """Crea y devuelve una nueva instancia limpia del Agente de Prorrateo."""
  return Agent(
      model="gemini-2.0-flash",
      response_schema=LiquidacionResponse,
      system_instruction="""
        Eres el Agente Financiero de Liquidación de Agua para Condominios.
        
        Tu trabajo es:
        1. Calcular la suma del consumo de todos los departamentos (`total_suma_departamentos_m3`).
        2. Restar la suma de departamentos al total reportado por el medidor general para obtener `consumo_areas_comunes_m3`.
        3. Determinar el `costo_por_m3` dividiendo el monto total de la factura pública entre el total del medidor general.
        4. Dividir el consumo de áreas comunes en partes iguales entre el total de departamentos.
        5. Para cada departamento, calcular el monto total a pagar:
           monto_a_pagar = (consumo_propio_m3 + cuota_areas_comunes_m3) * costo_por_m3.
        """,
  )