# =========================================
# SIMULADOR PTAR - PRODUCCIÓN (MEJORADO)
# =========================================

import time
import os
import numpy as np
from supabase import create_client

# =========================================
# CONFIG
# =========================================
SUPABASE_URL = "https://svomqhjdyyxubpiqmfex.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InN2b21xaGpkeXl4dWJwaXFtZmV4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzcwOTMwNDUsImV4cCI6MjA5MjY2OTA0NX0.B04htEJ0iTye5jOlUpbNq5nl4SdvVuXbQr0QgxkYjks"  # ⚠️ reemplaza por tu key real

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

INTERVALO = 300  # 5 min

# =========================================
# ESTADO GLOBAL
# =========================================
estado = {
    "nh4": 7.0,
    "no3": 2.5,
    "fase": "aireacion",
    "od_max": 4.2,
    "od_min": 0.3
}

# =========================================
# ACTUALIZAR FASE (CON HISTÉRESIS)
# =========================================
def actualizar_fase(od):

    fase = estado["fase"]

    if fase == "aireacion" and od >= estado["od_max"]:
        estado["fase"] = "transicion"

    elif fase == "transicion" and od <= 0.4:
        estado["fase"] = "anoxica"

    elif fase == "anoxica" and od >= (estado["od_min"] + 0.2):
        estado["fase"] = "aireacion"

        # 🔥 NUEVO CICLO → NUEVOS LÍMITES
        estado["od_max"] = np.random.uniform(3.8, 4.6)
        estado["od_min"] = np.random.uniform(0.15, 0.4)

# =========================================
# OD DINÁMICO (CLAVE)
# =========================================
def actualizar_od(prev_od):

    fase = estado["fase"]

    # velocidades variables
    vel_subida = np.random.uniform(0.02, 0.06)
    vel_bajada = np.random.uniform(0.08, 0.22)

    if fase == "aireacion":

        od = prev_od + vel_subida

        # curva más suave
        if od > 2:
            od += np.random.uniform(0.0, 0.03)

        od = min(od, estado["od_max"] + 0.3)

    elif fase == "transicion":

        od = prev_od - vel_bajada

        # caída más rápida al inicio
        if prev_od > 2.5:
            od -= np.random.uniform(0.05, 0.15)

        od = max(od, 0.3)

    else:  # anóxica

        # comportamiento no lineal
        od = prev_od - np.random.uniform(0.1, 0.3)

        # ligera recuperación biológica
        if od < 0.2:
            od += np.random.uniform(0.01, 0.05)

        od = max(od, 0)

    # 🔥 ruido sensor (muy importante)
    od += np.random.uniform(-0.04, 0.04)

    return max(0, od)

# =========================================
# MODELO GENERAL
# =========================================
def generar_estado(prev_od):

    od = actualizar_od(prev_od)
    actualizar_fase(od)
    fase = estado["fase"]

    # =========================================
    # NH4
    # =========================================
    if fase == "aireacion":
        nh4_target = 6 + (3.5 - od) * np.random.uniform(0.7, 1.0)

    elif fase == "transicion":
        nh4_target = 7.5 + (2.5 - od) * np.random.uniform(0.8, 1.2)

    else:
        nh4_target = 9.5 + np.random.uniform(0.5, 1.8)

    nh4 = np.clip(
        0.85 * estado["nh4"] + 0.15 * nh4_target,
        6.0,
        11.8
    )

    # =========================================
    # NO3
    # =========================================
    if fase == "aireacion":
        no3_target = 1.5 + (od * np.random.uniform(0.7, 1.0))

    elif fase == "transicion":
        no3_target = estado["no3"] - np.random.uniform(0.2, 0.6)

    else:
        no3_target = estado["no3"] - np.random.uniform(0.8, 1.6)

    no3 = 0.85 * estado["no3"] + 0.15 * np.clip(no3_target, 0.2, 6.5)

    # =========================================
    # NT
    # =========================================
    nt = nh4 + no3 + np.random.uniform(0.2, 0.7)

    estado["nh4"] = nh4
    estado["no3"] = no3

    return od, nh4, nt, no3, fase

# =========================================
# RECONEXIÓN
# =========================================
def reconnect():
    global supabase
    print("🔄 Reintentando conexión...")
    time.sleep(5)
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================
# OBTENER ÚLTIMO
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
# INSERT
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
# LOOP
# =========================================
def ejecutar():

    print("🚀 Simulador PTAR (Realista)")

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

            if insertar_dato(data):
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
