# =========================================
# SIMULADOR PTAR - PRODUCCIÓN (RENDER READY)
# =========================================

import time
import os
import numpy as np
from supabase import create_client

# =========================================
# CONFIG (ENV VARIABLES)
# =========================================
SUPABASE_URL = "https://svomqhjdyyxubpiqmfex.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN2b21xaGpkeXl4dWJwaXFtZmV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwOTMwNDUsImV4cCI6MjA5MjY2OTA0NX0.B04htEJ0iTye5jOlUpbNq5nl4SdvVuXbQr0QgxkYjks"  # ⚠️ reemplaza por tu key real

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Faltan variables de entorno SUPABASE")

# Cliente global
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

INTERVALO = 300  # segundos (5 min)

# =========================================
# ESTADO GLOBAL
# =========================================
estado = {
    "nh4": 7.0,
    "no3": 2.5,
    "fase": "aireacion"
}

# =========================================
# FASE
# =========================================
def actualizar_fase(od):
    fase = estado["fase"]

    if fase == "aireacion" and od >= 3.8:
        estado["fase"] = "transicion"

    elif fase == "transicion" and od <= 1.8:
        estado["fase"] = "anoxica"

    elif fase == "anoxica" and od <= 0.2:
        estado["fase"] = "aireacion"

# =========================================
# OD
# =========================================
def actualizar_od(prev_od):
    fase = estado["fase"]

    if fase == "aireacion":
        od = prev_od + np.random.uniform(0.015, 0.05)

        if od > 3:
            od += np.random.uniform(0.0, 0.02)

        if od < 1.5:
            od += 0.03

        od = min(od, 5.3)

    elif fase == "transicion":
        od = max(prev_od - np.random.uniform(0.08, 0.18), 1.6)

    else:
        od = prev_od - np.random.uniform(0.15, 0.35)

        if 0.5 < od < 2:
            od -= np.random.uniform(0.05, 0.15)

        od = max(od, 0)

    return od

# =========================================
# MODELO
# =========================================
def generar_estado(prev_od):
    od = actualizar_od(prev_od)
    actualizar_fase(od)
    fase = estado["fase"]

    # NH4
    if fase == "aireacion":
        nh4_target = 6 + (3.5 - od) * 0.8
    elif fase == "transicion":
        nh4_target = 7.5 + (2.5 - od)
    else:
        nh4_target = 9.5 + np.random.uniform(0.5, 1.5)

    nh4 = np.clip(0.85 * estado["nh4"] + 0.15 * nh4_target, 6.0, 11.5)

    # NO3
    if fase == "aireacion":
        no3_target = 1.5 + (od * 0.9)
    elif fase == "transicion":
        no3_target = estado["no3"] - np.random.uniform(0.2, 0.5)
    else:
        no3_target = estado["no3"] - np.random.uniform(0.8, 1.5)

    no3 = 0.85 * estado["no3"] + 0.15 * np.clip(no3_target, 0.2, 6.5)

    # NT
    nt = nh4 + no3 + np.random.uniform(0.2, 0.6)

    estado["nh4"] = nh4
    estado["no3"] = no3

    return od, nh4, nt, no3, fase

# =========================================
# RECONEXIÓN SEGURA
# =========================================
def reconnect():
    global supabase
    print("🔄 Reintentando conexión a Supabase...")
    time.sleep(5)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================
# OBTENER ÚLTIMOS DATOS
# =========================================
def obtener_ultimo_valor(columna, default):
    try:
        res = supabase.table("datos_ptar") \
            .select(columna) \
            .order("id", desc=True) \
            .limit(1) \
            .execute()

        if res.data and res.data[0][columna] is not None:
            return res.data[0][columna]

    except Exception as e:
        print(f"⚠️ Error leyendo {columna}:", e)

    return default

# =========================================
# INSERT SEGURO
# =========================================
def insertar_dato(data):
    try:
        supabase.table("datos_ptar").insert(data).execute()
        return True
    except Exception as e:
        print("❌ Error insertando:", e)
        reconnect()
        return False

# =========================================
# LOOP PRINCIPAL
# =========================================
def ejecutar():
    print("🚀 Simulador PTAR (Producción)")

    tiempo_simulado = int(obtener_ultimo_valor("tiempo_min", 0))

    while True:
        try:
            prev_od = obtener_ultimo_valor("od", 3.0)

            od, nh4, nt, no3, fase = generar_estado(prev_od)

            tiempo_simulado += INTERVALO / 60

            data = {
                "tiempo_min": int(tiempo_simulado),
                "od": round(float(od), 3),
                "nh4": round(float(nh4), 3),
                "no3": round(float(no3), 3),
                "nt": round(float(nt), 3)
            }

            ok = insertar_dato(data)

            if ok:
                print(
                    f"📊 [{fase.upper()}] "
                    f"T:{data['tiempo_min']} | "
                    f"OD:{data['od']} | NH4:{data['nh4']} | "
                    f"NO3:{data['no3']} | NT:{data['nt']}"
                )

        except Exception as e:
            print("🔥 Error crítico:", e)
            reconnect()

        time.sleep(INTERVALO)

# =========================================
# MAIN
# =========================================
if __name__ == "__main__":
    ejecutar()