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

async def guardar_lectura(departamento: str, lectura_m3: float, foto_url: str = None, incidencia: str = None):
    if not supabase:
        print("Warning: Supabase client is not initialized. Skipping database save.")
        return None
    data = {
        "departamento": departamento,
        "lectura_m3": lectura_m3,
        "foto_url": foto_url,
        "incidencia": incidencia
    }
    response = supabase.table("lecturas_agua").insert(data).execute()
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

