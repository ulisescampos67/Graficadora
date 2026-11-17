# -*- coding: utf-8 -*-
"""
=============================================================================
 NÚCLEO DEL GRAFICADOR CAD 2D (versión web)
 Diseño y Manufactura Asistido por Computadora (CAD/CAM)
=============================================================================
 Este archivo es Python y se ejecuta dentro del navegador con Pyodide.
 Contiene toda la matemática del programa:
   1. Primitivas (ecuaciones paramétricas de línea, arco, círculo y elipse)
   2. Matrices homogéneas 3x3 (traslación, rotación, escalado, simetría)
   3. Piezas paramétricas, cierre de contornos, área e interferencias
   4. Cotas, texto de ecuaciones y la función 'escena' que la página llama
 La página (JavaScript) solo dibuja en pantalla lo que este núcleo calcula.
 Es la misma matemática que graficador_cad.py, escrita en Python puro
 (sin NumPy) para que cargue rápido en el navegador.
=============================================================================
"""

import json
import math

N_PUNTOS = 200  # puntos con los que se discretiza cada entidad


# =============================================================================
# 1. PRIMITIVAS GEOMÉTRICAS (ecuaciones paramétricas) -> lista de (x, y)
# =============================================================================

def linea(x1, y1, x2, y2, n=2):
    """P(t) = P1 + t (P2 - P1),  0 <= t <= 1  (una recta solo necesita 2 puntos)."""
    return [(x1 + (x2 - x1) * i / (n - 1), y1 + (y2 - y1) * i / (n - 1)) for i in range(n)]


def arco(xc, yc, r, a1, a2, n=N_PUNTOS):
    """x = xc + r cos t,  y = yc + r sin t, de a1 a a2 grados (antihorario)."""
    if a2 <= a1:
        a2 += 360.0
    pts = []
    for i in range(n):
        t = math.radians(a1 + (a2 - a1) * i / (n - 1))
        pts.append((xc + r * math.cos(t), yc + r * math.sin(t)))
    return pts


def circulo(xc, yc, r, n=N_PUNTOS):
    return arco(xc, yc, r, 0.0, 360.0, n)


def elipse(xc, yc, a, b, inclinacion=0.0, n=N_PUNTOS):
    """x' = a cos t, y' = b sin t; después se gira 'inclinacion' y se lleva al centro."""
    phi = math.radians(inclinacion)
    c, s = math.cos(phi), math.sin(phi)
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / (n - 1)
        x, y = a * math.cos(t), b * math.sin(t)
        pts.append((xc + x * c - y * s, yc + x * s + y * c))
    return pts


# ---- Texto de las ecuaciones con los valores de cada figura ----

def _num(v):
    return f"{0.0 if abs(v) < 1e-12 else v:.4g}"


def _suma(a, b, termino):
    """'a + b·termino' cuidando signos, p. ej. (6, -6, 't') -> '6 − 6t'."""
    if abs(b) < 1e-12:
        return _num(a)
    coef = "" if abs(abs(b) - 1) < 1e-12 else _num(abs(b))
    parte = f"{coef}·{termino}" if coef and not termino.isalpha() else f"{coef}{termino}"
    if abs(a) < 1e-12:
        return ("−" if b < 0 else "") + parte
    return f"{_num(a)} {'−' if b < 0 else '+'} {parte}"


def ec_linea(x1, y1, x2, y2):
    return [f"x = {_suma(x1, x2 - x1, 't')},  y = {_suma(y1, y2 - y1, 't')}", "0 ≤ t ≤ 1"]


def ec_arco(xc, yc, r, a1, a2):
    return [f"x = {_suma(xc, r, 'cos t')}", f"y = {_suma(yc, r, 'sin t')}",
            f"{_num(a1)}° ≤ t ≤ {_num(a2)}°"]


def ec_circulo(xc, yc, r):
    return ec_arco(xc, yc, r, 0, 360)[:2] + ["0 ≤ t ≤ 2π"]


def ec_elipse(xc, yc, a, b, inclinacion=0.0):
    if abs(inclinacion) < 1e-12:
        return [f"x = {_suma(xc, a, 'cos t')}", f"y = {_suma(yc, b, 'sin t')}", "0 ≤ t ≤ 2π"]
    f = _num(inclinacion)
    return [f"x = {_num(xc)} + {_num(a)}cos t·cos{f}° − {_num(b)}sin t·sin{f}°",
            f"y = {_num(yc)} + {_num(a)}cos t·sin{f}° + {_num(b)}sin t·cos{f}°",
            "0 ≤ t ≤ 2π"]


# ---- Figura: nombre, tipo, puntos, ecuación y datos para el panel ----

def figura(nombre, tipo, pts, ecuacion, datos=None, centro=None):
    return {"nombre": nombre, "tipo": tipo, "pts": pts, "ec": ecuacion,
            "datos": datos, "centro": centro}


def nueva_linea(nombre, x1, y1, x2, y2):
    return figura(nombre, "Línea", linea(x1, y1, x2, y2), ec_linea(x1, y1, x2, y2))


def nuevo_arco(nombre, xc, yc, r, a1, a2):
    return figura(nombre, "Arco", arco(xc, yc, r, a1, a2), ec_arco(xc, yc, r, a1, a2),
                  centro=(xc, yc))


def nuevo_circulo(nombre, xc, yc, r):
    return figura(nombre, "Círculo", circulo(xc, yc, r), ec_circulo(xc, yc, r),
                  datos=(xc, yc, r), centro=(xc, yc))


def nueva_elipse(nombre, xc, yc, a, b, inclinacion=0.0):
    return figura(nombre, "Elipse", elipse(xc, yc, a, b, inclinacion),
                  ec_elipse(xc, yc, a, b, inclinacion), centro=(xc, yc))


# =============================================================================
# 2. MATRICES HOMOGÉNEAS 3x3: un punto (x, y) se escribe como [x, y, 1]
# =============================================================================

IDENTIDAD = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def mat_mul(A, B):
    """Producto de matrices 3x3: A · B."""
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def m_traslacion(tx, ty):
    return [[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]]


def m_rotacion(angulo, px=0.0, py=0.0):
    """M = T(p) · R(θ) · T(−p): rotación respecto al pivote p."""
    c, s = math.cos(math.radians(angulo)), math.sin(math.radians(angulo))
    R = [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]
    return mat_mul(mat_mul(m_traslacion(px, py), R), m_traslacion(-px, -py))


def m_escalado(sx, sy, px=0.0, py=0.0):
    """M = T(p) · S(sx, sy) · T(−p): escalado con punto fijo p."""
    S = [[sx, 0.0, 0.0], [0.0, sy, 0.0], [0.0, 0.0, 1.0]]
    return mat_mul(mat_mul(m_traslacion(px, py), S), m_traslacion(-px, -py))


def m_simetria_recta(x1, y1, x2, y2):
    """M = T(P1) · Ref(α) · T(−P1), con Ref(α) = [[cos2α, sin2α], [sin2α, −cos2α]]."""
    if math.hypot(x2 - x1, y2 - y1) < 1e-12:
        raise ValueError("Los dos puntos de la recta de simetría deben ser distintos")
    alfa = math.atan2(y2 - y1, x2 - x1)
    c, s = math.cos(2 * alfa), math.sin(2 * alfa)
    Ref = [[c, s, 0.0], [s, -c, 0.0], [0.0, 0.0, 1.0]]
    return mat_mul(mat_mul(m_traslacion(x1, y1), Ref), m_traslacion(-x1, -y1))


def aplicar(M, pts):
    """P' = M · P para cada punto [x, y, 1]."""
    return [(M[0][0] * x + M[0][1] * y + M[0][2], M[1][0] * x + M[1][1] * y + M[1][2])
            for x, y in pts]


def es_identidad(M):
    return all(abs(M[i][j] - IDENTIDAD[i][j]) < 1e-12 for i in range(3) for j in range(3))


def transformacion(tipo, p):
    """Regresa (M, descripción, fórmula general) del tipo pedido."""
    n = [_num(v) for v in p]
    if tipo == "traslacion":
        return m_traslacion(*p), f"Traslación  tx = {n[0]}, ty = {n[1]}", ["x' = x + tx", "y' = y + ty"]
    if tipo == "rotacion":
        return (m_rotacion(*p), f"Rotación  θ = {n[0]}°, pivote ({n[1]}, {n[2]})",
                ["M = T(p)·R(θ)·T(−p)", "x' = px + (x−px)cosθ − (y−py)sinθ",
                 "y' = py + (x−px)sinθ + (y−py)cosθ"])
    if tipo == "escalado":
        return (m_escalado(*p), f"Escalado  sx = {n[0]}, sy = {n[1]}, fijo ({n[2]}, {n[3]})",
                ["M = T(p)·S(sx, sy)·T(−p)", "x' = px + sx(x − px)", "y' = py + sy(y − py)"])
    if tipo == "eje_x":
        return [[1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]], "Simetría respecto al eje X", ["x' = x", "y' = −y"]
    if tipo == "eje_y":
        return [[-1.0, 0, 0], [0, 1.0, 0], [0, 0, 1.0]], "Simetría respecto al eje Y", ["x' = −x", "y' = y"]
    if tipo == "origen":
        return [[-1.0, 0, 0], [0, -1.0, 0], [0, 0, 1.0]], "Simetría respecto al origen", ["x' = −x", "y' = −y"]
    if tipo == "recta":
        alfa = math.degrees(math.atan2(p[3] - p[1], p[2] - p[0]))
        return (m_simetria_recta(*p), f"Simetría recta ({n[0]}, {n[1]})–({n[2]}, {n[3]})",
                ["M = T(P1)·Ref(α)·T(−P1)", f"α = atan2(y2−y1, x2−x1) = {alfa:.2f}°",
                 "Ref = [cos2α  sin2α; sin2α  −cos2α]"])
    raise ValueError(f"Transformación desconocida: {tipo}")


N_VALORES = {"traslacion": 2, "rotacion": 3, "escalado": 4, "recta": 4,
             "eje_x": 0, "eje_y": 0, "origen": 0}


def validar_transformacion(tipo, texto):
    """Revisa los valores escritos; regresa {'ok': [...]} o {'error': '...'}."""
    try:
        vals = [float(s) for s in texto.replace(",", " ").split()]
    except ValueError:
        return {"error": "Valores no válidos: escribe números separados por espacios"}
    if len(vals) != N_VALORES[tipo]:
        return {"error": f"Esta transformación pide {N_VALORES[tipo]} valores"}
    if tipo == "escalado" and (vals[0] == 0 or vals[1] == 0):
        return {"error": "Un factor de escala 0 aplasta la figura"}
    try:
        transformacion(tipo, vals)
    except ValueError as e:
        return {"error": str(e)}
    return {"ok": vals}


def texto_matriz(M, nombre="M"):
    filas = ["[" + " ".join(f"{_num(round(v, 3)):>7}" for v in fila) + " ]" for fila in M]
    sangria = " " * (len(nombre) + 3)
    return [sangria + filas[0], f"{nombre} = " + filas[1], sangria + filas[2]]


# =============================================================================
# 3. DISEÑO PARAMÉTRICO: piezas, cierre, área e interferencias
# =============================================================================

def pieza_con_arco(v):
    """Base, dos paredes y un arco superior. Cierra solo si R = L/2."""
    L, h, R, rb, a, b = (v[k] for k in ("L", "h", "R", "rb", "a", "b"))
    xc, s = L / 2, 0.09 * max(L, h + R)
    contorno = [nueva_linea("Línea base", 0, 0, L, 0), nueva_linea("Pared derecha", L, 0, L, h),
                nuevo_arco("Arco superior", xc, h, R, 0, 180), nueva_linea("Pared izquierda", 0, h, 0, 0)]
    internas = [nuevo_circulo("Barreno", xc, h, rb), nueva_elipse("Ranura", xc, h / 2, a, b)]
    cotas = [("lineal", (0, 0), (L, 0), -s, "L", L), ("lineal", (0, 0), (0, h), s, "h", h),
             ("radio", (xc, h), R, 135, "R", R), ("radio", (xc, h), rb, 45, "rb", rb),
             ("radio", (xc, h / 2), a, 0, "a", a)]
    return contorno, internas, cotas, []


def placa_redondeada(v):
    """Placa A x B con esquinas de radio r, 4 barrenos y una ventana elíptica."""
    A, B, r, rb, a, b = (v[k] for k in ("A", "B", "r", "rb", "a", "b"))
    s = 0.07 * max(A, B)
    contorno = [nueva_linea("Línea inferior", r, 0, A - r, 0), nuevo_arco("Arco inf. der.", A - r, r, r, 270, 360),
                nueva_linea("Línea derecha", A, r, A, B - r), nuevo_arco("Arco sup. der.", A - r, B - r, r, 0, 90),
                nueva_linea("Línea superior", A - r, B, r, B), nuevo_arco("Arco sup. izq.", r, B - r, r, 90, 180),
                nueva_linea("Línea izquierda", 0, B - r, 0, r), nuevo_arco("Arco inf. izq.", r, r, r, 180, 270)]
    internas = [nuevo_circulo(f"Barreno {i}", x, y, rb)
                for i, (x, y) in enumerate([(r, r), (A - r, r), (A - r, B - r), (r, B - r)], 1)]
    internas.append(nueva_elipse("Ventana", A / 2, B / 2, a, b))
    cotas = [("lineal", (0, 0), (A, 0), -s, "A", A), ("lineal", (0, 0), (0, B), s, "B", B),
             ("radio", (A - r, B - r), r, 45, "r", r), ("radio", (A - r, r), rb, 135, "rb", rb),
             ("radio", (A / 2, B / 2), a, 0, "a", a), ("radio", (A / 2, B / 2), b, 90, "b", b)]
    avisos = []
    if r > min(A, B) / 2:
        avisos.append(f"r no puede ser mayor que la mitad del lado menor ({_num(min(A, B) / 2)})")
    return contorno, internas, cotas, avisos


def ranura_obround(v):
    """Dos semicírculos unidos por rectas tangentes, con barrenos y ventana."""
    L, R, rb, a, b = (v[k] for k in ("L", "R", "rb", "a", "b"))
    contorno = [nueva_linea("Recta inferior", 0, -R, L, -R), nuevo_arco("Arco derecho", L, 0, R, 270, 450),
                nueva_linea("Recta superior", L, R, 0, R), nuevo_arco("Arco izquierdo", 0, 0, R, 90, 270)]
    internas = [nuevo_circulo("Barreno izq.", 0, 0, rb), nuevo_circulo("Barreno der.", L, 0, rb),
                nueva_elipse("Ventana", L / 2, 0, a, b)]
    cotas = [("lineal", (0, 0), (L, 0), -(R + 0.15 * (L + 2 * R)), "L", L),
             ("radio", (L, 0), R, 45, "R", R), ("radio", (0, 0), rb, 135, "rb", rb),
             ("radio", (L / 2, 0), a, 0, "a", a)]
    return contorno, internas, cotas, []


PIEZAS = {
    "Pieza con arco": {"parametros": [["L", "Ancho L", 6], ["h", "Altura h", 2.5], ["R", "Radio arco R", 3],
                                      ["rb", "R barreno rb", 0.8], ["a", "Ranura a", 1.8], ["b", "Ranura b", 0.35]],
                       "construir": pieza_con_arco, "cerrar": True},
    "Placa redondeada": {"parametros": [["A", "Ancho A", 8], ["B", "Alto B", 5], ["r", "Radio esquina r", 1],
                                        ["rb", "R barreno rb", 0.45], ["a", "Ventana a", 2], ["b", "Ventana b", 1]],
                         "construir": placa_redondeada, "cerrar": False},
    "Ranura (obround)": {"parametros": [["L", "Entre centros L", 6], ["R", "Radio R", 1.5],
                                        ["rb", "R barreno rb", 0.6], ["a", "Ventana a", 1.5], ["b", "Ventana b", 0.6]],
                         "construir": ranura_obround, "cerrar": False},
}


def catalogo():
    """Lista de piezas y sus medidas, para construir los controles de la página."""
    return json.dumps({n: p["parametros"] for n, p in PIEZAS.items()})


def cerrar_contorno(pieza, valores_json):
    """Aplica la restricción de cierre (pieza con arco: R = L/2)."""
    v = json.loads(valores_json)
    if not PIEZAS[pieza]["cerrar"]:
        return json.dumps({"mensaje": "Esta pieza se cierra sola: sus arcos se calculan con las otras medidas"})
    if abs(v["R"] - v["L"] / 2) < 1e-9:
        return json.dumps({"mensaje": "El contorno ya está cerrado"})
    v["R"] = v["L"] / 2
    return json.dumps({"valores": v, "mensaje": f"R ajustado a L/2 = {_num(v['R'])}"})


def holguras(contorno):
    """Distancia entre el final de cada entidad y el inicio de la siguiente."""
    n = len(contorno)
    return [math.dist(contorno[i]["pts"][-1], contorno[(i + 1) % n]["pts"][0]) for i in range(n)]


def area_poligono(p):
    """Fórmula del área de Gauss: A = ½ |Σ (x_i y_(i+1) − x_(i+1) y_i)|."""
    s = 0.0
    for i in range(len(p)):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % len(p)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def punto_dentro(poligono, x, y):
    """Método del rayo: dentro si un rayo horizontal cruza el borde un número impar de veces."""
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def interferencias(contorno, internas):
    """Cada figura interna debe quedar dentro del contorno y sin traslapes."""
    avisos = []
    borde = [p for f in contorno for p in f["pts"]]
    for f in internas:
        if not all(punto_dentro(borde, x, y) for x, y in f["pts"][::4]):
            avisos.append(f"{f['nombre']} se sale del contorno")
    for i, f in enumerate(internas):
        for g in internas[i + 1:]:
            if (any(punto_dentro(f["pts"], x, y) for x, y in g["pts"][::4])
                    or any(punto_dentro(g["pts"], x, y) for x, y in f["pts"][::4])):
                avisos.append(f"{f['nombre']} y {g['nombre']} se traslapan")
    return avisos


# =============================================================================
# 4. COTAS, ECUACIONES Y ESCENA COMPLETA
# =============================================================================

def geometria_cota(c, M):
    """Cota transformada con M: extensión, línea de cota, flechas y texto."""
    if c[0] == "lineal":
        _, p1, p2, d, nombre, valor = c
        L = math.dist(p1, p2)
        u = ((p2[0] - p1[0]) / L, (p2[1] - p1[1]) / L)
        n = (-u[1], u[0])
        q1, q2 = (p1[0] + d * n[0], p1[1] + d * n[1]), (p2[0] + d * n[0], p2[1] + d * n[1])
        P = aplicar(M, [p1, p2, q1, q2])
        ext, ini, fin, doble = [[P[0], P[2]], [P[1], P[3]]], P[2], P[3], True
        pos = ((ini[0] + fin[0]) / 2, (ini[1] + fin[1]) / 2)
    else:
        _, cen, r, ang, nombre, valor = c
        e = (cen[0] + r * math.cos(math.radians(ang)), cen[1] + r * math.sin(math.radians(ang)))
        ini, fin = aplicar(M, [cen, e])
        ext, doble = [], False
        pos = (ini[0] + 0.6 * (fin[0] - ini[0]), ini[1] + 0.6 * (fin[1] - ini[1]))
    real = math.dist(ini, fin)
    texto = f"{nombre} = {_num(valor)}" + ("" if abs(real - valor) < 1e-6 else f" → {_num(real)}")
    return {"ext": ext, "ini": ini, "fin": fin, "doble": doble, "pos": pos, "texto": texto}


def lineas_ecuaciones(figuras):
    """Una línea por entidad; los círculos seguidos de igual radio se agrupan."""
    L, i = [], 0
    while i < len(figuras):
        f = figuras[i]
        grupo = [f]
        while (f["tipo"] == "Círculo" and i + len(grupo) < len(figuras)
               and figuras[i + len(grupo)]["tipo"] == "Círculo"
               and abs(figuras[i + len(grupo)]["datos"][2] - f["datos"][2]) < 1e-9):
            grupo.append(figuras[i + len(grupo)])
        if len(grupo) == 1:
            L.append(f"{f['nombre']}: " + ";  ".join(f["ec"]))
        else:
            r = _num(f["datos"][2])
            base = f["nombre"].rstrip("0123456789 .")
            resto = f["nombre"][len(base):].strip()
            nombre = (f"{f['nombre']}–{grupo[-1]['nombre'][len(base):].strip()}" if resto.isdigit()
                      else " / ".join(g["nombre"] for g in grupo))
            L.append(f"{nombre}: x = xc + {r}·cos t;  y = yc + {r}·sin t;  0 ≤ t ≤ 2π")
            L.append("   (xc, yc) = " + "  ".join(f"({_num(g['datos'][0])}, {_num(g['datos'][1])})" for g in grupo))
        i += len(grupo)
    return L


def figura_libre(d):
    """Construye una figura dibujada con el mouse a partir de sus clics."""
    tipo, c, nombre = d["tipo"], d["clics"], d["nombre"]
    (x0, y0), (x1, y1) = c[0], c[1]
    r = math.hypot(x1 - x0, y1 - y0)
    if tipo == "Línea":
        return nueva_linea(nombre, x0, y0, x1, y1)
    if tipo == "Círculo":
        return nuevo_circulo(nombre, x0, y0, r)
    if tipo == "Arco":
        a1 = math.degrees(math.atan2(y1 - y0, x1 - x0))
        a2 = math.degrees(math.atan2(c[2][1] - y0, c[2][0] - x0))
        return nuevo_arco(nombre, x0, y0, r, a1, a2)
    ux, uy = (x1 - x0) / r, (y1 - y0) / r                      # elipse
    b = abs(ux * (c[2][1] - y0) - uy * (c[2][0] - x0))
    return nueva_elipse(nombre, x0, y0, r, b, math.degrees(math.atan2(uy, ux)))


def validar_clics(tipo, clics_json):
    """Revisa que los clics definan una figura válida antes de crearla."""
    c = json.loads(clics_json)
    if math.dist(c[0], c[1]) < 1e-12:
        return "Los dos primeros puntos coinciden; vuelve a intentarlo"
    if tipo == "Elipse":
        (x0, y0), (x1, y1) = c[0], c[1]
        r = math.dist(c[0], c[1])
        if abs((x1 - x0) / r * (c[2][1] - y0) - (y1 - y0) / r * (c[2][0] - x0)) < 1e-12:
            return "El tercer punto está sobre el eje mayor; b no puede ser 0"
    return ""


def escena(estado_json):
    """Recibe el estado de la página y regresa todo lo que se debe dibujar."""
    e = json.loads(estado_json)
    pieza_visible = e["ver"]["Pieza"]
    contorno, internas, cotas, avisos = PIEZAS[e["pieza"]]["construir"](e["valores"])
    if not pieza_visible:
        contorno, internas, cotas, avisos = [], [], [], []
    figuras = contorno + internas

    # matriz acumulada de la pieza: la nueva multiplica por la izquierda
    pila = [transformacion(t["tipo"], t["vals"]) for t in e["pila"]]
    M = IDENTIDAD
    for t in pila:
        M = mat_mul(t[0], M)
    for f in figuras:
        f["M"] = M
    libres = []
    for d in e["libres"]:                         # cada dibujo: solo lo posterior a él
        f = figura_libre(d)
        f["M"] = IDENTIDAD
        for t in pila[min(d["desde"], len(pila)):]:
            f["M"] = mat_mul(t[0], f["M"])
        libres.append(f)
    for f in figuras + libres:
        f["actual"] = aplicar(f["M"], f["pts"])
        f["transformada"] = not es_identidad(f["M"])

    # uniones del contorno y extremos sueltos del dibujo
    tol = 1e-7 * max([1.0] + [abs(c) for f in figuras + libres for p in f["pts"] for c in p])
    hol = holguras(contorno) if contorno else [0.0]
    ok, cruces = [], []
    for i, hueco in enumerate(hol if contorno else []):
        fin, ini = contorno[i]["actual"][-1], contorno[(i + 1) % len(contorno)]["actual"][0]
        (ok.append(fin) if hueco <= tol else cruces.extend([fin, ini]))
    extremos = [(f["actual"][k], j) for j, f in enumerate(libres) if f["tipo"] in ("Línea", "Arco") for k in (0, -1)]
    anclas = [f["actual"][k] for f in contorno for k in (0, -1)]
    sueltos = []
    for j, (p, _) in enumerate(extremos):
        otros = [q for k, (q, _) in enumerate(extremos) if k != j] + anclas
        (ok if any(math.dist(p, q) <= max(tol, 1e-9) for q in otros) else sueltos).append(p)

    # puntos a los que se pega el imán
    notables = [f["actual"][k] for f in libres if f["tipo"] in ("Línea", "Arco") for k in (0, -1)]
    notables += [aplicar(f["M"], [f["centro"]])[0] for f in libres if f["centro"]]
    notables += [f["actual"][0] for f in contorno]

    # estado del contorno
    if not pieza_visible:
        estado = {"clase": "neutro", "titulo": "Pieza oculta", "detalle": "Botón «Pieza» apagado"}
    elif max(hol) <= tol:
        area = area_poligono([p for f in contorno for p in f["actual"]])
        area -= sum(area_poligono(f["actual"]) for f in internas)
        perim = sum(math.dist(f["actual"][i], f["actual"][i + 1]) for f in contorno for i in range(len(f["actual"]) - 1))
        estado = {"clase": "ok", "titulo": f"Contorno CERRADO · {len(contorno)} entidades",
                  "detalle": f"Área neta = {area:.3f} u²   Perímetro = {perim:.3f} u"}
    else:
        estado = {"clase": "mal", "titulo": f"Contorno ABIERTO · holgura máx. = {_num(max(hol))}",
                  "detalle": "Área no definida" + (" → usa «Cerrar contorno»" if PIEZAS[e["pieza"]]["cerrar"] else "")}
    if pieza_visible:
        avisos = avisos + interferencias(contorno, internas)
    if libres:
        abiertas = sum(f["tipo"] in ("Línea", "Arco") for f in libres)
        txt = (f"{len(sueltos)} extremo(s) suelto(s)" if sueltos
               else "sin extremos sueltos" if abiertas else "solo figuras cerradas")
        avisos.insert(0, f"Dibujo libre: {len(libres)} entidad(es) · {txt}")

    # panel de ecuaciones y matrices
    P = []
    if figuras:
        P += ["ECUACIONES PARAMÉTRICAS (pieza original)"] + lineas_ecuaciones(figuras)
    if libres:
        P += ([""] if P else []) + ["DIBUJO LIBRE (antes de transformar)"] + lineas_ecuaciones(libres)
    if not P:
        P = ["Sin figuras: muestra la pieza o dibuja con el mouse"]
    P += ["", "TRANSFORMACIONES (orden de aplicación)"]
    if not pila:
        P.append("  ninguna: M = I (identidad)")
    else:
        P += [f"  {i}. {t[1]}" for i, t in enumerate(pila, 1)]
        P += ["Última:  " + pila[-1][2][0]] + ["         " + s for s in pila[-1][2][1:]]
        P += ["Matriz acumulada:"] + texto_matriz(M) + ["P'(t) = M · P(t)"]

    todas = figuras + libres
    return json.dumps({
        "curvas": [{"tipo": f["tipo"], "pts": f["actual"]} for f in todas],
        "originales": [f["pts"] for f in todas if f["transformada"]] if e["ver"]["Original"] else [],
        "ok": ok, "cruces": cruces, "sueltos": sueltos, "notables": notables,
        "ejes": [t["vals"] for t in e["pila"] if t["tipo"] == "recta"],
        "cotas": [geometria_cota(c, M) for c in cotas] if e["ver"]["Cotas"] else [],
        "estado": estado, "avisos": avisos[:4], "panel": "\n".join(P),
        "titulo": (e["pieza"] if pieza_visible else "Dibujo libre") + "  ·  " +
                  (f"{len(pila)} transformación(es)" if pila else "posición original"),
        "vacio": not todas,
    })


def prueba():
    """Mismos casos de verificación que el programa de escritorio."""
    casos = [(aplicar(m_traslacion(3, 2), [(1, 0)])[0], (4, 2)),
             (aplicar(m_rotacion(90), [(1, 0)])[0], (0, 1)),
             (aplicar(m_rotacion(180, 2, 0), [(1, 0)])[0], (3, 0)),
             (aplicar(m_escalado(2, 3), [(1, 1)])[0], (2, 3)),
             (aplicar(transformacion("eje_x", [])[0], [(1, 5)])[0], (1, -5)),
             (aplicar(transformacion("eje_y", [])[0], [(1, 5)])[0], (-1, 5)),
             (aplicar(m_simetria_recta(0, 0, 1, 1), [(1, 5)])[0], (5, 1))]
    ok = all(math.dist(a, b) < 1e-9 for a, b in casos)
    M = m_simetria_recta(8, -1, 9, 6)
    ok &= es_identidad(mat_mul(M, M))
    return f"{sum(math.dist(a, b) < 1e-9 for a, b in casos) + 1}/8 pruebas correctas" if ok else "HAY ERRORES"
