import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime, date

st.set_page_config(
    page_title="Simulador de Precios, Ofertas y Auditoría",
    page_icon="💊",
    layout="wide"
)

# Archivo persistente para el historial
ARCHIVO_HISTORIAL = "historial_ofertas.csv"

# ------------------------------------------------------------------
# ESTILOS CSS: TARJETAS IDÉNTICAS Y ALERTA DE PÉRDIDA
# ------------------------------------------------------------------
st.markdown("""
<style>
    .kpi-container {
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        border-radius: 12px;
        padding: 16px 18px;
        color: white;
        height: 150px;
        min-height: 150px;
        max-height: 150px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        box-sizing: border-box;
    }
    .kpi-title {
        font-size: 0.80rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 700;
        opacity: 0.92;
        line-height: 1.2;
        min-height: 32px;
    }
    .kpi-value {
        font-size: 1.80rem;
        font-weight: 800;
        line-height: 1.1;
        margin: 4px 0;
    }
    .kpi-sub {
        font-size: 0.76rem;
        opacity: 0.88;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .bg-blue   { background: linear-gradient(135deg, #1d4ed8, #3b82f6); }
    .bg-green  { background: linear-gradient(135deg, #047857, #10b981); }
    .bg-red    { background: linear-gradient(135deg, #b91c1c, #ef4444); }
    .bg-purple { background: linear-gradient(135deg, #6d28d9, #8b5cf6); }
    .bg-amber  { background: linear-gradient(135deg, #b45309, #f59e0b); }
    
    .caja-perdida {
        border-left: 5px solid #ef4444;
        background-color: #fee2e2;
        color: #991b1b;
        padding: 14px 18px;
        border-radius: 8px;
        margin-top: 15px;
        margin-bottom: 15px;
    }

    div[data-testid="stButton"] button {
        width: 100%;
        padding: 5px 0px;
        font-weight: 700;
        font-size: 1.0rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# FUNCIONES AUXILIARES DE MONEDA Y FORMATO ARGENTINO
# ------------------------------------------------------------------
def parsear_monto(texto_input) -> float:
    if texto_input is None:
        return 0.0
    if isinstance(texto_input, (int, float)):
        return float(texto_input)
    
    txt = str(texto_input).strip()
    if not txt:
        return 0.0
    
    txt = re.sub(r"[^\d,\.-]", "", txt)
    if "." in txt and "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    elif "," in txt:
        txt = txt.replace(",", ".")
    elif "." in txt:
        partes = txt.split(".")
        if len(partes[-1]) == 3 and len(partes) > 1:
            txt = "".join(partes)
            
    try:
        return float(txt)
    except ValueError:
        return 0.0

def parsear_flotante(texto_input, default=1.43) -> float:
    if texto_input is None:
        return default
    if isinstance(texto_input, (int, float)):
        return float(texto_input)
    txt = str(texto_input).strip().replace(",", ".")
    try:
        return float(txt)
    except ValueError:
        return default

def formato_pesos(numero: float) -> str:
    if numero is None:
        return "$ 0,00"
    parte_entera = f"{int(abs(numero)):,}".replace(",", ".")
    parte_decimal = f"{abs(numero):.2f}".split(".")[1]
    signo = "-" if numero < 0 else ""
    return f"{signo}$ {parte_entera},{parte_decimal}"

# ------------------------------------------------------------------
# PERSISTENCIA DEL HISTORIAL
# ------------------------------------------------------------------
def cargar_historial() -> pd.DataFrame:
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            df = pd.read_csv(ARCHIVO_HISTORIAL)
            df["Fecha_DT"] = pd.to_datetime(df["Fecha_Hora"]).dt.date
            return df
        except Exception:
            pass
    return pd.DataFrame(columns=[
        "ID", "Fecha_Hora", "Rubro", "Producto", "Costo_Sin_IVA", 
        "Coeficiente", "Oferta_Pct", "Margen_Objetivo_Pct", "Precio_Lista_Actual", 
        "Nuevo_Precio_Sugerido", "Aumento_Pct", "Aumento_Dinero", "Precio_Oferta_Publico"
    ])

def guardar_registro(item: dict):
    df = cargar_historial()
    nuevo_df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
    if "Fecha_DT" in nuevo_df.columns:
        nuevo_df = nuevo_df.drop(columns=["Fecha_DT"])
    nuevo_df.to_csv(ARCHIVO_HISTORIAL, index=False)

# ------------------------------------------------------------------
# ESTADOS DE SESIÓN (VALOR INICIAL COEFICIENTE: 1.43)
# ------------------------------------------------------------------
if "coef_str" not in st.session_state:
    st.session_state.coef_str = "1.43"

if "desc_val" not in st.session_state:
    st.session_state.desc_val = 20.0

if "margen_val" not in st.session_state:
    st.session_state.margen_val = 25.0

if "iva_val" not in st.session_state:
    st.session_state.iva_val = 21.0

# ------------------------------------------------------------------
# BARRA LATERAL: ⚙️ CONFIGURACIÓN
# ------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración")

# 1. Coeficiente de Variación
st.sidebar.markdown("**🔘 Coeficiente de Variación**")
col_m1, col_t1, col_p1 = st.sidebar.columns([1, 2.3, 1])
with col_m1:
    if st.button("➖", key="btn_coef_minus"):
        v = parsear_flotante(st.session_state.coef_str, default=1.43)
        st.session_state.coef_str = f"{max(1.0, v - 0.01):.2f}"
        st.rerun()
with col_p1:
    if st.button("➕", key="btn_coef_plus"):
        v = parsear_flotante(st.session_state.coef_str, default=1.43)
        st.session_state.coef_str = f"{v + 0.01:.2f}"
        st.rerun()
with col_t1:
    txt_c = st.text_input(
        "coef_txt",
        value=st.session_state.coef_str,
        label_visibility="collapsed",
        help="Escribí números del 0 al 9 directamente"
    )
    st.session_state.coef_str = txt_c

coeficiente = parsear_flotante(st.session_state.coef_str, default=1.43)

# 2. Descuento de Oferta (%)
st.sidebar.markdown("**🏷️ Oferta / Descuento (%)**")
col_m2, col_t2, col_p2 = st.sidebar.columns([1, 2.3, 1])
with col_m2:
    if st.button("➖", key="btn_desc_minus"):
        st.session_state.desc_val = max(0.0, st.session_state.desc_val - 1.0)
        st.rerun()
with col_p2:
    if st.button("➕", key="btn_desc_plus"):
        st.session_state.desc_val = min(90.0, st.session_state.desc_val + 1.0)
        st.rerun()
with col_t2:
    txt_d = st.text_input(
        "desc_txt",
        value=f"{st.session_state.desc_val:.1f}",
        label_visibility="collapsed"
    )
    st.session_state.desc_val = parsear_flotante(txt_d, default=20.0)

descuento_oferta_pct = st.session_state.desc_val

# 3. Rentabilidad a Mantener (%)
st.sidebar.markdown("**🛡️ Rentabilidad a Mantener (%)**")
col_m3, col_t3, col_p3 = st.sidebar.columns([1, 2.3, 1])
with col_m3:
    if st.button("➖", key="btn_margen_minus"):
        st.session_state.margen_val = max(0.0, st.session_state.margen_val - 1.0)
        st.rerun()
with col_p3:
    if st.button("➕", key="btn_margen_plus"):
        st.session_state.margen_val = st.session_state.margen_val + 1.0
        st.rerun()
with col_t3:
    txt_m = st.text_input(
        "margen_txt",
        value=f"{st.session_state.margen_val:.1f}",
        label_visibility="collapsed"
    )
    st.session_state.margen_val = parsear_flotante(txt_m, default=25.0)

margen_mantener_pct = st.session_state.margen_val

# 4. Alícuota IVA (%)
st.sidebar.markdown("**🏛️ Alícuota IVA (%)**")
col_m4, col_t4, col_p4 = st.sidebar.columns([1, 2.3, 1])
with col_m4:
    if st.button("➖", key="btn_iva_minus"):
        st.session_state.iva_val = max(0.0, st.session_state.iva_val - 0.5)
        st.rerun()
with col_p4:
    if st.button("➕", key="btn_iva_plus"):
        st.session_state.iva_val = min(50.0, st.session_state.iva_val + 0.5)
        st.rerun()
with col_t4:
    txt_i = st.text_input(
        "iva_txt",
        value=f"{st.session_state.iva_val:.1f}",
        label_visibility="collapsed"
    )
    st.session_state.iva_val = parsear_flotante(txt_i, default=21.0)

iva_pct = st.session_state.iva_val

# ------------------------------------------------------------------
# MOTOR MATEMÁTICO
# ------------------------------------------------------------------
i = iva_pct / 100.0
d = descuento_oferta_pct / 100.0
m_objetivo = margen_mantener_pct / 100.0

margen_base_pct = (coeficiente - 1.0) * 100.0
descuento_quiebre_pct = ((coeficiente - 1.0) / coeficiente) * 100.0 if coeficiente > 0 else 0.0
margen_sin_remarcar_pct = (coeficiente * (1.0 - d) - 1.0) * 100.0

# Detección de pérdida
esta_en_perdida = descuento_oferta_pct > descuento_quiebre_pct
exceso_descuento_pct = max(0.0, descuento_oferta_pct - descuento_quiebre_pct)

st.title("💊 Tablero de Precios, Ofertas y Trazabilidad")

# ------------------------------------------------------------------
# PARÁMETROS DE INTERÉS (TARJETAS UNIFORMES)
# ------------------------------------------------------------------
st.markdown("#### 📌 Parámetros de Interés del Escenario Actual")

es_saludable = (margen_mantener_pct >= 10.0) and (margen_sin_remarcar_pct >= 0.0)
color_margen = "bg-green" if es_saludable else "bg-red"
icono_margen = "🟢" if es_saludable else "🔴"
estado_texto = "Saludable" if es_saludable else "⚠️ En Riesgo / Pérdida"

color_quiebre = "bg-red" if esta_en_perdida else "bg-amber"
sub_quiebre = f"🚨 Superado por +{exceso_descuento_pct:.2f}%" if esta_en_perdida else "Descuento máx. sin perder"

col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

with col_kpi1:
    st.markdown(f"""
    <div class="kpi-container bg-blue">
        <div class="kpi-title">🏷️ Descuento Aplicado</div>
        <div class="kpi-value">{descuento_oferta_pct:.1f}%</div>
        <div class="kpi-sub">Promoción en mostrador</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi2:
    st.markdown(f"""
    <div class="kpi-container {color_margen}">
        <div class="kpi-title">{icono_margen} Margen Rentabilidad</div>
        <div class="kpi-value">{margen_mantener_pct:.1f}%</div>
        <div class="kpi-sub">{estado_texto}</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi3:
    st.markdown(f"""
    <div class="kpi-container {color_quiebre}">
        <div class="kpi-title">🚨 Umbral de Pérdida</div>
        <div class="kpi-value">{descuento_quiebre_pct:.2f}%</div>
        <div class="kpi-sub">{sub_quiebre}</div>
    </div>
    """, unsafe_allow_html=True)

with col_kpi4:
    st.markdown(f"""
    <div class="kpi-container bg-purple">
        <div class="kpi-title">🔘 Coef. de Variación</div>
        <div class="kpi-value">{coeficiente}</div>
        <div class="kpi-sub">Rentabilidad base: +{margen_base_pct:.1f}%</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# ------------------------------------------------------------------
# PESTAÑAS: SIMULADOR Y AUDITORÍA
# ------------------------------------------------------------------
tab_simulador, tab_auditoria = st.tabs(["⚡ Calculadora y Guardado de Ofertas", "📋 Reporte y Auditoría de Trazabilidad"])

LISTA_RUBROS = [
    "perfumeria/fragancias",
    "marroquineria",
    "dermatologia",
    "cosmetica",
    "herboristeria",
    "ortopedia",
    "accesorios varios"
]

# ==================================================================
# PESTAÑA 1: CALCULADORA, CUANTIFICACIÓN DE PÉRDIDA Y GUARDADO
# ==================================================================
with tab_simulador:
    col_izq, col_der = st.columns([1, 1.2])

    with col_izq:
        st.subheader("1. Producto a Evaluar")
        prod_nombre = st.text_input("Descripción del Producto", value="Termo Keep 1.5LT")
        
        costo_raw = st.text_input(
            "Costo Sin IVA ($)", 
            value="$ 4.395,35", 
            help="Admite formatos como $ 4.395,35 o 4395,35"
        )
        costo_sin_iva = parsear_monto(costo_raw)
        precio_actual_lista_con_iva = (costo_sin_iva * coeficiente) * (1 + i)

        # Cálculos de remarcación previa
        precio_lista_nuevo_con_iva = (costo_sin_iva * (1 + m_objetivo) * (1 + i)) / (1 - d) if (1 - d) > 0 else 0
        diferencia_dinero = precio_lista_nuevo_con_iva - precio_actual_lista_con_iva
        porcentaje_aumento = ((precio_lista_nuevo_con_iva / precio_actual_lista_con_iva) - 1) * 100 if precio_actual_lista_con_iva > 0 else 0
        precio_mostrador_oferta = precio_lista_nuevo_con_iva * (1 - d)

        # Cálculos en caso de que NO se remarque la lista:
        precio_oferta_sin_remarcar = precio_actual_lista_con_iva * (1 - d)
        precio_neto_sin_remarcar = precio_oferta_sin_remarcar / (1 + i)
        resultado_sin_remarcar = precio_neto_sin_remarcar - costo_sin_iva
        pct_perdida = (resultado_sin_remarcar / costo_sin_iva) * 100 if costo_sin_iva > 0 else 0

        st.info(
            f"📦 **Producto:** {prod_nombre}\n\n"
            f"• Costo sin IVA: **{formato_pesos(costo_sin_iva)}**\n\n"
            f"• Precio de lista vigente (Coef. {coeficiente}): **{formato_pesos(precio_actual_lista_con_iva)}**"
        )

        st.markdown("---")
        st.markdown("##### 📂 Guardar en Historial de Ofertas")
        rubro_seleccionado = st.selectbox(
            "Seleccioná el Rubro del Producto:",
            LISTA_RUBROS
        )

        if st.button("💾 Guardar Oferta y Trazabilidad", use_container_width=True):
            ahora = datetime.now()
            registro = {
                "ID": ahora.strftime("%Y%m%d%H%M%S"),
                "Fecha_Hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                "Rubro": rubro_seleccionado,
                "Producto": prod_nombre,
                "Costo_Sin_IVA": round(costo_sin_iva, 2),
                "Coeficiente": round(coeficiente, 4),
                "Oferta_Pct": round(descuento_oferta_pct, 2),
                "Margen_Objetivo_Pct": round(margen_mantener_pct, 2),
                "Precio_Lista_Actual": round(precio_actual_lista_con_iva, 2),
                "Nuevo_Precio_Sugerido": round(precio_lista_nuevo_con_iva, 2),
                "Aumento_Pct": round(porcentaje_aumento, 2),
                "Aumento_Dinero": round(diferencia_dinero, 2),
                "Precio_Oferta_Publico": round(precio_mostrador_oferta, 2)
            }
            guardar_registro(registro)
            st.success(f"✅ ¡Guardado con éxito! Se registró bajo **'{rubro_seleccionado}'** el {ahora.strftime('%d/%m/%Y a las %H:%M')}.")

    with col_der:
        st.subheader("2. Remarcación y Precio Final")
        
        c_aum_pct, c_aum_pesos = st.columns(2)
        with c_aum_pct:
            st.metric(
                label="📈 Porcentaje a Aumentar",
                value=f"{porcentaje_aumento:+.2f}%".replace(".", ","),
                delta="Ajuste requerido en lista",
                delta_color="inverse"
            )
        with c_aum_pesos:
            st.metric(
                label="💵 Dinero a Aumentar (por unidad)",
                value=formato_pesos(diferencia_dinero),
                delta="Monto a sumar a la lista",
                delta_color="inverse"
            )

        st.markdown("---")
        
        c_pl1, c_pl2 = st.columns(2)
        with c_pl1:
            st.write("**Precio de Lista Actual:**")
            st.markdown(f"### {formato_pesos(precio_actual_lista_con_iva)}")
            st.caption(f"Costo × {coeficiente} + {iva_pct:.1f}% IVA")
        with c_pl2:
            st.write("**NUEVO Precio de Lista Sugerido:**")
            st.markdown(f"<h2 style='color:#059669; margin:0;'>{formato_pesos(precio_lista_nuevo_con_iva)}</h2>", unsafe_allow_html=True)
            st.caption("Cargar este precio en el sistema.")

        st.markdown("---")
        
        precio_neto_sin_iva = precio_mostrador_oferta / (1 + i)
        ganancia_neta_pesos = precio_neto_sin_iva - costo_sin_iva
        margen_efectivo_real = (ganancia_neta_pesos / costo_sin_iva) * 100 if costo_sin_iva > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("Precio con Descuento", formato_pesos(precio_mostrador_oferta))
        m2.metric("Ganancia Neta Unitaria", formato_pesos(ganancia_neta_pesos))
        m3.metric("Rentabilidad Asegurada", f"{margen_efectivo_real:.2f}%".replace(".", ","))

        # ----------------------------------------------------------
        # CUANTIFICACIÓN DE PÉRDIDA SI SE SUPERA EL UMBRAL
        # ----------------------------------------------------------
        if esta_en_perdida:
            perdida_unitaria = abs(resultado_sin_remarcar)
            pct_perdida_costo = abs(pct_perdida)
            
            st.markdown(f"""
            <div class="caja-perdida">
                <h4 style="margin:0 0 8px 0; color:#991b1b;">🚨 ¡ATENCIÓN: OFERTA POR ENCIMA DEL UMBRAL DE PÉRDIDA!</h4>
                La oferta del <b>{descuento_oferta_pct:.1f}%</b> supera el umbral límite del <b>{descuento_quiebre_pct:.2f}%</b> (exceso de <b>+{exceso_descuento_pct:.2f}%</b>).<br>
                <b>Si aplicás esta oferta SIN remarcar la lista, estarás trabajando A PÉRDIDA:</b><br>
                <ul style="margin: 8px 0;">
                    <li><b>Pérdida neta por unidad:</b> <span style="font-size:1.15rem; font-weight:bold;">{formato_pesos(perdida_unitaria)}</span> por debajo de tu costo.</li>
                    <li><b>Destrucción de capital:</b> Estás perdiendo un <b>{pct_perdida_costo:.2f}%</b> de tu costo de reposición en cada venta.</li>
                    <li><b>Cobro neto en caja:</b> Recibirías neto <b>{formato_pesos(precio_neto_sin_remarcar)}</b> frente a un costo de <b>{formato_pesos(costo_sin_iva)}</b>.</li>
                </ul>
                👉 <b>Solución obligatoria:</b> Para no perder dinero y además ganar tu <b>{margen_mantener_pct:.0f}%</b> pretendido, 
                debés remarcar la lista obligatoriamente a <b>{formato_pesos(precio_lista_nuevo_con_iva)}</b> (aumento de <b>{formato_pesos(diferencia_dinero)}</b>).
            </div>
            """, unsafe_allow_html=True)

            # Simulador de volumen de pérdida
            with st.expander("📊 Calcular pérdida acumulada según unidades vendidas"):
                unidades = st.number_input("Cantidad de unidades vendidas en la oferta:", min_value=1, value=10, step=5)
                perdida_total = perdida_unitaria * unidades
                st.error(f"💸 Vendiendo **{unidades} unidades** sin remarcar, la pérdida directa de bolsillo será de **{formato_pesos(perdida_total)}**.")
        else:
            if diferencia_dinero > 0:
                st.warning(
                    f"💡 **Recomendación**: Remarcá la lista en **{formato_pesos(diferencia_dinero)}** "
                    f"(un **+{porcentaje_aumento:.2f}%**). Así, cuando apliques el **{descuento_oferta_pct:.0f}%** de oferta, "
                    f"el cliente paga **{formato_pesos(precio_mostrador_oferta)}** y asegurás tu **{margen_mantener_pct:.0f}%** de rentabilidad neta."
                )
            else:
                st.success(
                    f"✅ Con tu coeficiente de **{coeficiente}** no hace falta remarcar. "
                    f"El precio actual cubre el descuento del {descuento_oferta_pct:.0f}% sin comprometer la rentabilidad deseada."
                )

# ==================================================================
# PESTAÑA 2: REPORTE Y AUDITORÍA DE TRAZABILIDAD
# ==================================================================
with tab_auditoria:
    st.subheader("📋 Registro Histórico y Auditoría de Trazabilidad")
    st.caption("Filtra las ofertas guardadas por rango de calendario y rubro para auditar remarcaciones y descargar reportes.")

    df_hist = cargar_historial()

    if df_hist.empty:
        st.info("ℹ️ Todavía no hay ofertas guardadas. Guardá tu primer producto desde la calculadora.")
    else:
        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 2])
        
        fechas_disponibles = pd.to_datetime(df_hist["Fecha_Hora"]).dt.date
        fecha_min = fechas_disponibles.min()
        fecha_max = fechas_disponibles.max()

        with col_f1:
            f_desde = st.date_input("Fecha Desde:", value=fecha_min, min_value=fecha_min, max_value=date.today())
        with col_f2:
            f_hasta = st.date_input("Fecha Hasta:", value=fecha_max, min_value=fecha_min, max_value=date.today())
        with col_f3:
            rubro_filtro = st.selectbox("Filtrar por Rubro:", ["Todos los rubros"] + LISTA_RUBROS)

        # Filtros
        df_hist["Fecha_DT"] = pd.to_datetime(df_hist["Fecha_Hora"]).dt.date
        mask = (df_hist["Fecha_DT"] >= f_desde) & (df_hist["Fecha_DT"] <= f_hasta)
        if rubro_filtro != "Todos los rubros":
            mask = mask & (df_hist["Rubro"] == rubro_filtro)
        
        df_filtrado = df_hist[mask].copy()

        st.markdown("---")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Ofertas Auditadas", len(df_filtrado))
        
        aum_prom = df_filtrado["Aumento_Pct"].mean() if not df_filtrado.empty else 0.0
        aum_max = df_filtrado["Aumento_Pct"].max() if not df_filtrado.empty else 0.0
        rubro_top = df_filtrado["Rubro"].mode()[0] if not df_filtrado.empty else "-"

        a2.metric("Remarcación Promedio", f"{aum_prom:+.2f}%".replace(".", ","))
        a3.metric("Remarcación Máxima", f"{aum_max:+.2f}%".replace(".", ","))
        a4.metric("Rubro con más Ofertas", rubro_top)

        st.markdown("---")

        df_vista = df_filtrado.copy()
        df_vista["Costo_Sin_IVA"] = df_vista["Costo_Sin_IVA"].apply(formato_pesos)
        df_vista["Precio_Lista_Actual"] = df_vista["Precio_Lista_Actual"].apply(formato_pesos)
        df_vista["Nuevo_Precio_Sugerido"] = df_vista["Nuevo_Precio_Sugerido"].apply(formato_pesos)
        df_vista["Aumento_Dinero"] = df_vista["Aumento_Dinero"].apply(formato_pesos)
        df_vista["Precio_Oferta_Publico"] = df_vista["Precio_Oferta_Publico"].apply(formato_pesos)
        df_vista["Aumento_Pct"] = df_vista["Aumento_Pct"].apply(lambda x: f"{x:+.2f}%".replace(".", ","))
        df_vista["Oferta_Pct"] = df_vista["Oferta_Pct"].apply(lambda x: f"{x:.1f}%".replace(".", ","))
        df_vista["Margen_Objetivo_Pct"] = df_vista["Margen_Objetivo_Pct"].apply(lambda x: f"{x:.1f}%".replace(".", ","))

        columnas_mostrar = [
            "Fecha_Hora", "Rubro", "Producto", "Costo_Sin_IVA", "Coeficiente",
            "Oferta_Pct", "Precio_Lista_Actual", "Nuevo_Precio_Sugerido",
            "Aumento_Pct", "Aumento_Dinero", "Precio_Oferta_Publico"
        ]

        st.dataframe(
            df_vista[columnas_mostrar],
            use_container_width=True,
            hide_index=True
        )

        csv_data = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte de Auditoría (CSV / Excel)",
            data=csv_data,
            file_name=f"auditoria_ofertas_{f_desde}_al_{f_hasta}.csv",
            mime="text/csv"
        )