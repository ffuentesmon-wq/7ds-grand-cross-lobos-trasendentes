import time
import random
import cv2
import numpy as np
import os
import subprocess
import sys
from ppadb.client import Client as AdbClient

# Librerías para la ventana emergente al inicio
import tkinter as tk
from tkinter import simpledialog, messagebox

# ==========================================
# INTERFAZ INICIAL - CONFIGURACIÓN DE OBJETIVO
# ==========================================
def pedir_objetivo_runs():
    root = tk.Tk()
    root.withdraw() 
    
    objetivo = simpledialog.askinteger(
        "Configuración del Bot", 
        "¿Cuántas runs con victoria quieres completar hoy?:", 
        initialvalue=5, 
        minvalue=1
    )
    
    if objetivo is None:
        print("[Bot] Inicio cancelado por el usuario.")
        sys.exit()
        
    print(f"[Objetivo] El bot se detendrá automáticamente tras completar {objetivo} victorias (contando desde la segunda run).")
    return objetivo

RUNS_OBJETIVO = pedir_objetivo_runs()
runs_completadas = 0
primera_run_saltada = False

# ==========================================
# CONFIGURACIÓN DE ADB Y BLUESTACKS
# ==========================================
PUERTO_BLUESTACKS = 5555

def conectar_adb():
    print("[ADB] Comprobando servidor ADB...")
    ruta_adb_bluestacks = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
    
    if os.path.exists(ruta_adb_bluestacks):
        try:
            subprocess.run([ruta_adb_bluestacks, "start-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("[ADB] Servidor local iniciado correctamente desde BlueStacks.")
        except Exception as e:
            print(f"[ADB] Aviso al iniciar servidor: {e}")
    else:
        print("[ADB] Alerta: No se encontró HD-Adb.exe en la ruta por defecto. Intentando conectar de todos modos...")

    try:
        client = AdbClient(host="127.0.0.1", port=5037)
        client.remote_connect("127.0.0.1", PUERTO_BLUESTACKS)
        dispositivo = client.device(f"127.0.0.1:{PUERTO_BLUESTACKS}")
        
        if dispositivo:
            print("[ADB] ¡Conexión exitosa con el emulador!")
            return dispositivo
        else:
            raise Exception("Dispositivo no encontrado tras la conexión remota.")
    except Exception as e:
        print("\n" + "="*60)
        print(" ERROR DE CONEXIÓN CRÍTICO ")
        print("="*60)
        raise e

device = conectar_adb()

# ==========================================
# MAPEOS DE CARTAS Y VARIABLES GLOBALES
# ==========================================

# --- FASE 1 ---
CONJUNTO_F1_RIGIDO = ["s1_thonar.png", "s1_roxy.png", "s1_subaru.png", "s2_riyo.png"]

# --- FASE 2 ---
CONJUNTO_1_F2 = ["s1_thonar.png", "s1_riyo.png", "ulty_riyo.png", "ulty_thonar.png", "ulty_roxy.png", "s1_subaru.png", "s1_roxy.png"]
CONJUNTO_2_F2 = ["s2_subaru.png", "s2_riyo.png", "s2_roxy.png", "s2_thonar.png"]

# --- FASE 3 ---
CONJUNTO_1_F3 = ["ulty_riyo.png", "ulty_roxy.png", "ulty_thonar.png", "s1_thonar.png", "s1_riyo.png", "s1_subaru.png", "s1_roxy.png"]
CONJUNTO_2_F3 = ["s2_subaru.png", "s2_riyo.png", "s2_roxy.png", "s2_thonar.png"]
CONJUNTO_3_F3 = ["s2_thonar.png", "s2_riyo.png", "s2_roxy.png", "s2_subaru.png", "s1_roxy.png", "s1_subaru.png", "s1_riyo.png", "s1_thonar.png"]

ultima_fase_detectada = None
contador_fase_atascada = 0
LIMITE_ATASCADO = 20  
MAX_CARTAS_POR_TURNO = 4

# --- BANDERAS PARA CLIC ÚNICO POR FASE ---
ya_hizo_clic_lobo_f1 = False
ya_hizo_clic_lobo_f2 = False

# ==========================================
# DETECCIÓN DE IMÁGENES Y CLICS INTERNOS (ADB)
# ==========================================

def capturar_pantalla_emulador():
    resultado = device.screencap()
    img_np = np.frombuffer(resultado, np.uint8)
    return cv2.imdecode(img_np, cv2.IMREAD_COLOR)

def localizar_en_emulador(imagen_objetivo, confidence=0.70):
    pantalla = capturar_pantalla_emulador()
    plantilla = cv2.imread(imagen_objetivo, cv2.IMREAD_COLOR)
    
    if plantilla is None:
        return None
        
    res = cv2.matchTemplate(pantalla, plantilla, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val >= confidence:
        h, w, _ = plantilla.shape
        return (max_loc[0], max_loc[1], w, h, max_val)
    return None

def localizar_mas_a_la_derecha(imagen_objetivo, confidence=0.75):
    pantalla = capturar_pantalla_emulador()
    plantilla = cv2.imread(imagen_objetivo, cv2.IMREAD_COLOR)
    
    if plantilla is None:
        return None
        
    h, w, _ = plantilla.shape
    res = cv2.matchTemplate(pantalla, plantilla, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val < confidence:
        return None  
        
    loc = np.where(res >= confidence)
    puntos = list(zip(loc[1], loc[0]))
    
    if not puntos:
        return (max_loc[0], max_loc[1], w, h, max_val)
        
    puntos_unicos = []
    for p in sorted(puntos, key=lambda x: x[0], reverse=True):
        if not puntos_unicos:
            puntos_unicos.append(p)
        else:
            if all(abs(int(p[0]) - int(u[0])) > 15 or abs(int(p[1]) - int(u[1])) > 15 for u in puntos_unicos):
                puntos_unicos.append(p)
                
    if puntos_unicos:
        mejor_x, mejor_y = puntos_unicos[0]
        return (int(mejor_x), int(mejor_y), w, h, max_val)
        
    return (max_loc[0], max_loc[1], w, h, max_val)

def localizar_mas_a_la_izquierda(imagen_objetivo, confidence=0.75):
    pantalla = capturar_pantalla_emulador()
    plantilla = cv2.imread(imagen_objetivo, cv2.IMREAD_COLOR)
    
    if plantilla is None:
        return None
        
    h, w, _ = plantilla.shape
    res = cv2.matchTemplate(pantalla, plantilla, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    
    if max_val < confidence:
        return None  
        
    loc = np.where(res >= confidence)
    puntos = list(zip(loc[1], loc[0]))
    
    if not puntos:
        return (max_loc[0], max_loc[1], w, h, max_val)
        
    puntos_unicos = []
    for p in sorted(puntos, key=lambda x: x[0], reverse=False):
        if not puntos_unicos:
            puntos_unicos.append(p)
        else:
            if all(abs(int(p[0]) - int(u[0])) > 15 or abs(int(p[1]) - int(u[1])) > 15 for u in puntos_unicos):
                puntos_unicos.append(p)
                
    if puntos_unicos:
        mejor_x, mejor_y = puntos_unicos[0]
        return (int(mejor_x), int(mejor_y), w, h, max_val)
        
    return (max_loc[0], max_loc[1], w, h, max_val)

# ==========================================
# FUNCIONES DE DETECCIÓN POR ZONA (ROI) PARA LOBOS
# ==========================================
def detectar_y_cliquear_lobo_dorado():
    pantalla = capturar_pantalla_emulador()
    x_min, y_min = 403, 437
    x_max, y_max = 466, 533
    
    pantalla_recortada = pantalla[y_min:y_max, x_min:x_max]
    plantilla = cv2.imread("lobo_dorado.png", cv2.IMREAD_COLOR)
    
    if plantilla is None:
        return False

    pantalla_gris = cv2.cvtColor(pantalla_recortada, cv2.COLOR_BGR2GRAY)
    plantilla_gris = cv2.cvtColor(plantilla, cv2.COLOR_BGR2GRAY)
    
    pantalla_norm = cv2.equalizeHist(pantalla_gris)
    plantilla_norm = cv2.equalizeHist(plantilla_gris)
    
    res = cv2.matchTemplate(pantalla_norm, plantilla_norm, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    
    print(f"[Fase 1] lobo_dorado en zona: {float(max_val) * 100:.2f}%")
    
    if float(max_val) >= 0.70:
        print(f"✅ ¡[Fase 1] Lobo dorado detectado ({float(max_val) * 100:.2f}%)! Dando clic...")
        CAJA_DORADO = (403, 437, 63, 96)
        clic_en_zona_aleatoria(CAJA_DORADO)
        return True
    return False

def detectar_y_cliquear_lobo_plateado():
    pantalla = capturar_pantalla_emulador()
    x_min, y_min = 171, 460
    x_max, y_max = 234, 601
    
    pantalla_recortada = pantalla[y_min:y_max, x_min:x_max]
    plantilla = cv2.imread("lobo_plateado.png", cv2.IMREAD_COLOR)
    
    if plantilla is None:
        return False

    pantalla_gris = cv2.cvtColor(pantalla_recortada, cv2.COLOR_BGR2GRAY)
    plantilla_gris = cv2.cvtColor(plantilla, cv2.COLOR_BGR2GRAY)
    
    pantalla_norm = cv2.equalizeHist(pantalla_gris)
    plantilla_norm = cv2.equalizeHist(plantilla_gris)
    
    res = cv2.matchTemplate(pantalla_norm, plantilla_norm, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    
    print(f"[Fase 2] lobo_plateado en zona: {float(max_val) * 100:.2f}%")
    
    if float(max_val) >= 0.70:
        print(f"✅ ¡[Fase 2] Lobo plateado detectado ({float(max_val) * 100:.2f}%)! Dando clic...")
        CAJA_PLATEADO = (171, 460, 63, 141)
        clic_en_zona_aleatoria(CAJA_PLATEADO)
        return True
    return False

def espera_humana():
    base = random.uniform(2.2, 3.5)
    variacion = random.uniform(-0.3, 0.3)
    return max(1.5, base + variacion)

def clic_en_zona_aleatoria(posicion_caja):
    left, top, width, height = posicion_caja[:4]
    
    margen_x = int(width * 0.20)
    margen_y = int(height * 0.20)
    
    min_x = left + margen_x
    max_x = left + width - margen_x
    min_y = top + margen_y
    max_y = top + height - margen_y
    
    rand_x = random.randint(min_x, max(min_x, max_x))
    rand_y = random.randint(min_y, max(min_y, max_y))

    time.sleep(0.2) 
    device.shell(f"input tap {rand_x} {rand_y}")
    
    segundos_pausa = espera_humana()
    print(f"[Clic Registrado] Coordenadas: X={rand_x}, Y={rand_y} | Pausa: {segundos_pausa:.2f}s")
    
    time.sleep(segundos_pausa)

# ==========================================
# LÓGICA DE CONTROL DE TURNO Y ACCIONES
# ==========================================

def ejecutar_clics_turno_fijos(verificar_reinicio=False):
    left, top, width, height = (850, 480, 100, 60)
    rand_x = random.randint(left, left + width)
    rand_y = random.randint(top, top + height)
    
    pausa_rapida = random.uniform(0.3, 0.7)
    
    print(f"[Pasar Turno] Fin de conjunto/cartas. Clic rápido en X={rand_x}, Y={rand_y} | Pausa micro: {pausa_rapida:.2f}s")
    device.shell(f"input tap {rand_x} {rand_y}")
    time.sleep(pausa_rapida)
    
    if verificar_reinicio:
        verificar_y_hacer_clic_reinicio()

def verificar_y_hacer_clic_reinicio():
    try:
        pos_reinicio = localizar_en_emulador("reinicio.png", confidence=0.70)
        if pos_reinicio:
            print("[Reinicio] ¡Carta de reinicio detectada! Haciendo clic...")
            clic_en_zona_aleatoria(pos_reinicio)
            return True
    except Exception:
        pass
    return False

def ejecutar_secuencia_retirada():
    print("[Anti-Bloqueo] Iniciando secuencia de retirada por atascamiento...")
    try:
        pos_pausa = localizar_en_emulador("pausa.png", confidence=0.70)
        if pos_pausa:
            clic_en_zona_aleatoria(pos_pausa)
            pos_retirada = localizar_en_emulador("retirada.png", confidence=0.70) or localizar_en_emulador("retiradaestra.png", confidence=0.70)

            if pos_retirada:
                clic_en_zona_aleatoria(pos_retirada)
                pos_aceptar = localizar_en_emulador("aceptarretirada.png", confidence=0.70)
                if pos_aceptar:
                    clic_en_zona_aleatoria(pos_aceptar)
                    return True
    except Exception as e:
        print(f"[Error Secuencia] Excepción durante la retirada: {e}")
    return False

def controlling_atascamiento(fase_actual):
    global ultima_fase_detectada, contador_fase_atascada
    if ultima_fase_detectada == fase_actual:
        contador_fase_atascada += 1
        print(f"[Monitoreo] Fase '{fase_actual}' consecutiva. Contador: {contador_fase_atascada}/{LIMITE_ATASCADO}")
    else:
        ultima_fase_detectada = fase_actual
        contador_fase_atascada = 1

    if contador_fase_atascada >= LIMITE_ATASCADO:
        print(f"[ALERTA] ¡Atascado en '{fase_actual}'!")
        if ejecutar_secuencia_retirada():
            contador_fase_atascada = 0

# ==========================================
# BUCLE PRINCIPAL
# ==========================================
while True:
    try:
        puntuaciones_fases = {}
        pantalla_actual = capturar_pantalla_emulador()
        
        for num_fase in ["fase1", "fase2", "fase3"]:
            archivo = f"{num_fase}.png"
            plantilla = cv2.imread(archivo, cv2.IMREAD_COLOR)
            if plantilla is not None:
                res = cv2.matchTemplate(pantalla_actual, plantilla, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(res)
                h, w, _ = plantilla.shape
                puntuaciones_fases[num_fase] = {"val": max_val, "pos": (max_loc[0], max_loc[1], w, h)}
            else:
                puntuaciones_fases[num_fase] = {"val": 0.0, "pos": None}

        fase_ganadora = max(puntuaciones_fases, key=lambda k: puntuaciones_fases[k]["val"])
        mejor_puntuacion = puntuaciones_fases[fase_ganadora]["val"]

        if mejor_puntuacion >= 0.75:
            print(f"[Análisis] Fase identificada: {fase_ganadora.upper()} (Coincidencia: {mejor_puntuacion*100:.1f}%)")
            
            # ----------------------------------------------------
            # EJECUCIÓN FASE 1
            # ----------------------------------------------------
            if fase_ganadora == "fase1":
                controlling_atascamiento("Fase 1")
                if localizar_en_emulador("miturno.png", confidence=0.70):
                    print("¡Es mi turno en la Fase 1!")

                    if not ya_hizo_clic_lobo_f1:
                        print("[Fase 1] Buscando lobo_dorado.png (Modo persistente hasta >= 70%)...")
                        while not ya_hizo_clic_lobo_f1:
                            if detectar_y_cliquear_lobo_dorado():
                                ya_hizo_clic_lobo_f1 = True
                                break
                            time.sleep(0.8)
                    else:
                        print("[Fase 1] El enemigo ya recibió su clic reglamentario en esta fase.")

                    cartas_lanzadas = 0
                    for carta in CONJUNTO_F1_RIGIDO:
                        if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                            break
                            
                        posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                        if posicion_actual:
                            print(f"[Fase 1 - Rígido] Lanzando: {carta} (Confianza: {posicion_actual[4]*100:.1f}%)")
                            clic_en_zona_aleatoria(posicion_actual)
                            cartas_lanzadas += 1
                            contador_fase_atascada = 0

                    if cartas_lanzadas < MAX_CARTAS_POR_TURNO and localizar_en_emulador("miturno.png", confidence=0.70):
                        ejecutar_clics_turno_fijos(verificar_reinicio=(cartas_lanzadas == 0))

            # ----------------------------------------------------
            # EJECUCIÓN FASE 2
            # ----------------------------------------------------
            elif fase_ganadora == "fase2":
                controlling_atascamiento("Fase 2")
                if localizar_en_emulador("miturno.png", confidence=0.70):
                    print("¡Es mi turno en la Fase 2!")

                    if not ya_hizo_clic_lobo_f2:
                        print("[Fase 2] Buscando lobo_plateado.png (Modo persistente hasta >= 70%)...")
                        while not ya_hizo_clic_lobo_f2:
                            if detectar_y_cliquear_lobo_plateado():
                                ya_hizo_clic_lobo_f2 = True
                                break
                            time.sleep(0.8)
                    else:
                        print("[Fase 2] El enemigo ya recibió su clic reglamentario en esta fase.")

                    cartas_lanzadas = 0

                    # AGOTAR CONJUNTO 1 EN FASE 2
                    for carta in CONJUNTO_1_F2:
                        if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                            break
                        
                        if carta == "s1_thonar.png":
                            posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                            if posicion_actual:
                                print(f"[Fase 2 - C1] Lanzando ÚNICA copia de: {carta}")
                                clic_en_zona_aleatoria(posicion_actual)
                                cartas_lanzadas += 1
                                contador_fase_atascada = 0
                        else:
                            while cartas_lanzadas < MAX_CARTAS_POR_TURNO:
                                posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                                if posicion_actual:
                                    print(f"[Fase 2 - C1] Agotando copia de: {carta} (Confianza: {posicion_actual[4]*100:.1f}%)")
                                    clic_en_zona_aleatoria(posicion_actual)
                                    cartas_lanzadas += 1
                                    contador_fase_atascada = 0
                                else:
                                    break  

                    # AGOTAR CONJUNTO 2 EN FASE 2
                    if cartas_lanzadas < MAX_CARTAS_POR_TURNO:
                        for carta in CONJUNTO_2_F2:
                            if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                                break
                            
                            if carta == "s1_thonar.png":
                                posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                                if posicion_actual:
                                    print(f"[Fase 2 - C2] Lanzando ÚNICA copia de: {carta}")
                                    clic_en_zona_aleatoria(posicion_actual)
                                    cartas_lanzadas += 1
                                    contador_fase_atascada = 0
                            else:
                                while cartas_lanzadas < MAX_CARTAS_POR_TURNO:
                                    posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                                    if posicion_actual:
                                        print(f"[Fase 2 - C2] Agotando copia de: {carta} (Confianza: {posicion_actual[4]*100:.1f}%)")
                                        clic_en_zona_aleatoria(posicion_actual)
                                        cartas_lanzadas += 1
                                        contador_fase_atascada = 0
                                    else:
                                        break

                    if cartas_lanzadas < MAX_CARTAS_POR_TURNO and localizar_en_emulador("miturno.png", confidence=0.70):
                        ejecutar_clics_turno_fijos(verificar_reinicio=(cartas_lanzadas == 0))

            # ----------------------------------------------------
            # EJECUCIÓN FASE 3
            # ----------------------------------------------------
            elif fase_ganadora == "fase3":
                controlling_atascamiento("Fase 3")
                if localizar_en_emulador("miturno.png", confidence=0.70):
                    print("¡Es mi turno en la Fase 3!")
                    
                    cartas_lanzadas = 0
                    indicador_detectado = localizar_en_emulador("indicador_subaru.png", confidence=0.70)
                    
                    if indicador_detectado:
                        print("[Fase 3] ¡Indicador de Subaru detectado! Priorizando y agotando CONJUNTO_3_F3...")
                        
                        for carta in CONJUNTO_3_F3:
                            if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                                break
                            
                            if carta == "s2_thonar.png":
                                posicion_actual = localizar_mas_a_la_derecha(carta, confidence=0.70)
                                if posicion_actual:
                                    print(f"[Fase 3 - Especial] Lanzando ÚNICA copia de: {carta}")
                                    clic_en_zona_aleatoria(posicion_actual)
                                    cartas_lanzadas += 1
                                    contador_fase_atascada = 0
                            else:
                                while cartas_lanzadas < MAX_CARTAS_POR_TURNO:
                                    posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                                    if posicion_actual:
                                        print(f"[Fase 3 - Especial] Agotando copia de: {carta}")
                                        clic_en_zona_aleatoria(posicion_actual)
                                        cartas_lanzadas += 1
                                        contador_fase_atascada = 0
                                    else:
                                        break  
                    else:
                        # FASE 3 NORMAL: Se usa la función para priorizar la de más a la izquierda para s2_thonar.png
                        for carta in CONJUNTO_1_F3:
                            if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                                break
                            posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                            if posicion_actual:
                                print(f"[Fase 3 - C1] Lanzando: {carta}")
                                clic_en_zona_aleatoria(posicion_actual)
                                cartas_lanzadas += 1
                                contador_fase_atascada = 0

                        if cartas_lanzadas < MAX_CARTAS_POR_TURNO:
                            for carta in CONJUNTO_2_F3:
                                if cartas_lanzadas >= MAX_CARTAS_POR_TURNO:
                                    break
                                
                                if carta == "s2_thonar.png":
                                    posicion_actual = localizar_mas_a_la_izquierda(carta, confidence=0.70)
                                    if posicion_actual:
                                        print(f"[Fase 3 - C2] Lanzando s2_thonar (Más a la izquierda): {carta}")
                                        clic_en_zona_aleatoria(posicion_actual)
                                        cartas_lanzadas += 1
                                        contador_fase_atascada = 0
                                else:
                                    posicion_actual = localizar_en_emulador(carta, confidence=0.70)
                                    if posicion_actual:
                                        print(f"[Fase 3 - C2] Lanzando: {carta}")
                                        clic_en_zona_aleatoria(posicion_actual)
                                        cartas_lanzadas += 1
                                        contador_fase_atascada = 0

                    if cartas_lanzadas < MAX_CARTAS_POR_TURNO and localizar_en_emulador("miturno.png", confidence=0.70):
                        ejecutar_clics_turno_fijos(verificar_reinicio=(cartas_lanzadas == 0))

        # ----------------------------------------------------
        # MENÚS GENERALES Y REINICIO DE BANDERAS DE CLIC
        # ----------------------------------------------------
        else:
            botones_menu = ["menuvictoria.png", "aceptarvictoria.png", "aceptarderrota.png", "menuderrota.png", "usar.png", "comenzar.png", "aceptarusarelemento.png"]
            encontrado = False
            for boton in botones_menu:
                pos = localizar_en_emulador(boton, confidence=0.70)
                if pos:
                    print(f"Detectado menú: {boton}. Ejecutando clic...")
                    clic_en_zona_aleatoria(pos)
                    contador_fase_atascada = 0
                    encontrado = True
                    
                    if boton in ["menuvictoria.png", "menuderrota.png", "aceptarderrota.png", "comenzar.png"]:
                        ya_hizo_clic_lobo_f1 = False
                        ya_hizo_clic_lobo_f2 = False
                        print("[Control de Fases] Permisos de clics a enemigos restaurados para la nueva run.")
                    
                    if boton == "menuvictoria.png":
                        if not primera_run_saltada:
                            print("="*60)
                            print(" ¡PRIMERA RUN COMPLETADA (Omitida del contador por configuración)! ")
                            print("="*60)
                            primera_run_saltada = True
                        else:
                            runs_completadas += 1
                            print("="*60)
                            print(f" ¡RUN COMPLETADA! (Progreso: {runs_completadas}/{RUNS_OBJETIVO})")
                            print("="*60)
                            
                            if runs_completadas >= RUNS_OBJETIVO:
                                root = tk.Tk()
                                root.withdraw()
                                messagebox.showinfo("Bot Finalizado", f"¡Objetivo cumplido!\nSe completaron con éxito {runs_completadas} runs.")
                                sys.exit()
                    break
            
            if not encontrado:
                print("Ninguna fase o botón detectado, analizando siguiente frame...")

    except Exception as e:
        print("Error en bucle principal:", e)

    time.sleep(1.2)
