import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = None

# Only initialize if valid URL and Key are provided (and not placeholders)
if SUPABASE_URL and SUPABASE_KEY and SUPABASE_URL not in ("", "TU_SUPABASE_URL") and SUPABASE_KEY not in ("", "TU_SUPABASE_SERVICE_ROLE_KEY"):
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase client: {e}")
else:
    print("Warning: Supabase credentials not configured or are using placeholders. Database features will be disabled.")

async def guardar_lectura(departamento_id: str, respuesta_agente: dict, foto_url: str = None):
    if not supabase:
        print("Warning: Supabase client is not initialized. Skipping database save.")
        return None
    data = {
        "departamento_id": departamento_id,
        "lectura_anterior": respuesta_agente.get("lectura_anterior", 0),
        "lectura_actual": respuesta_agente.get("lectura_actual", 0),
        "consumo_m3": respuesta_agente["consumo_m3"],
        "alerta": respuesta_agente["alerta"],
        "tipo_alerta": respuesta_agente.get("tipo_alerta"),
        "mensaje_observacion": respuesta_agente["mensaje"],
        "foto_url": foto_url
    }
    response = supabase.table("lecturas").insert(data).execute()
    return response.data

async def guardar_liquidacion(liquidacion_data: dict):
    if not supabase:
        print("Warning: Supabase client is not initialized. Skipping database save.")
        return None
    response = supabase.table("liquidaciones").insert(liquidacion_data).execute()
    return response.data

async def guardar_recibos_generados(recibos_data: dict):
    if not supabase:
        print("Warning: Supabase client is not initialized. Skipping database save.")
        return None
    response = supabase.table("recibos_emitidos").insert(recibos_data).execute()
    return response.data

