import streamlit as st
import pandas as pd
import os
import shutil
import glob
import re
from datetime import datetime, date
import io
from PIL import Image

st.set_page_config(
    page_title="Tablero de Precios, Ofertas y Rentabilidad",
    page_icon="💊",
    layout="wide"
)

# ------------------------------------------------------------------
# 1. FUNCIONES AUXILIARES Y PERSISTENCIA (AL TOPE PARA EVITAR ERRORES)
# ------------------------------------------------------------------
ARCHIVO_HISTORIAL = "historial_ofertas.csv"
ARCHIVO_RESPALDO = "respaldo_emergencia_copelco.csv"
LOGO_OFICIAL = "logo_copelco_oficial.png"

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

def parsear_flotante(texto_input, default=1.3) -> float:
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

def cargar_historial() -> pd.DataFrame:
    df = pd.DataFrame()
    if os.path.exists(ARCHIVO_HISTORIAL):
        try:
            df = pd.read_csv(ARCHIVO_HISTORIAL)
        except Exception:
            pass
    if df.empty and os.path.exists(ARCHIVO_RESPALDO):
        try:
            df = pd.read_csv(ARCHIVO_RESPALDO)
            df.to_csv(ARCHIVO_HISTORIAL, index=False)
        except Exception:
            pass
    if not df.empty:
        if "Codigo" not in df.columns:
            df["Codigo"] = "-"
        if "Fecha_Hora" in df.columns:
            df["Fecha_DT"] = pd.to_datetime(df["Fecha_Hora"]).dt.date
        return df
    return pd.DataFrame(columns=[
        "ID", "Fecha_Hora", "Rubro", "Codigo", "Producto", "Costo_Sin_IVA", 
        "Coeficiente", "Oferta_Pct", "Margen_Objetivo_Pct", "Precio_Lista_Actual", 
        "Nuevo_Precio_Sugerido", "Aumento_Pct", "Aumento_Dinero", "Precio_Oferta_Publico"
    ])

def guardar_registro(item: dict):
    df = cargar_historial()
    nuevo_df = pd.concat([df, pd.DataFrame([item])], ignore_index=True)
    if "Fecha_DT" in nuevo_df.columns:
        nuevo_df = nuevo_df.drop(columns=["Fecha_DT"])
    nuevo_df.to_csv(ARCHIVO_HISTORIAL, index=False)
    nuevo_df.to_csv(ARCHIVO_RESPALDO, index=False)

def eliminar_registro_por_id(id_reg):
    df = cargar_historial()
    if not df.empty and "ID" in df.columns:
        df_filtrado = df[df["ID"].astype(str).str.strip() != str(id_reg).strip()]
        if "Fecha_DT" in df_filtrado.columns:
            df_filtrado = df_filtrado.drop(columns=["Fecha_DT"])
        df_filtrado.to_csv(ARCHIVO_HISTORIAL, index=False)
        df_filtrado.to_csv(ARCHIVO_RESPALDO, index=False)

def vaciar_historial_completo():
    if os.path.exists(ARCHIVO_HISTORIAL):
        os.remove(ARCHIVO_HISTORIAL)
    if os.path.exists(ARCHIVO_RESPALDO):
        os.remove(ARCHIVO_RESPALDO)

def obtener_ruta_logo():
    if os.path.exists(LOGO_OFICIAL):
        return LOGO_OFICIAL
    candidatos = glob.glob("*.jpg") + glob.glob("*.png") + glob.glob("*.jpeg")
    for c in candidatos:
        if any(k in c.lower() for k in ["logo", "images", "copelco", "8"]):
            try:
                img = Image.open(c)
                img.save(LOGO_OFICIAL)
                return LOGO_OFICIAL
            except Exception:
                pass
    if candidatos:
        try:
            img = Image.open(candidatos[0])
            img.save(LOGO_OFICIAL)
            return LOGO_OFICIAL
        except Exception:
            pass
    return None

# ------------------------------------------------------------------
# LIBRERÍA DE PDF (REPORTLAB)
# ------------------------------------------------------------------
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

def generar_pdf_auditoria(df_data: pd.DataFrame, f_desde, f_hasta) -> bytes:
    if not HAS_REPORTLAB:
        return b""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=20, leftMargin=20, topMargin=25, bottomMargin=25)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=14, textColor=colors.HexColor('#1d4ed8'), spaceAfter=6)
    story.append(Paragraph("Informe Gerencial de Auditoría y Rentabilidad de Ofertas - Farmacia Social Copelco", title_style))
    story.append(Paragraph(f"<b>Período:</b> {f_desde} al {f_hasta} | <b>Total Registros:</b> {len(df_data)}", styles['Normal']))
    story.append(Spacer(1, 10))
    table_data = [["Segmento", "Código", "Producto", "Precio Costo", "Precio Lista", "Rentab. (Coef.)", "Oferta", "Rentab. Post", "Nuevo Precio"]]
    df_ordenado = df_data.sort_values(by="Rubro")
    for _, row in df_ordenado.iterrows():
        coef_val = float(row['Coeficiente'])
        margen_obj = float(row['Margen_Objetivo_Pct'])
        table_data.append([
            str(row['Rubro']).title(),
            str(row.get('Codigo', '-')),
            str(row['Producto'])[:22],
            f"${row['Costo_Sin_IVA']:,.2f}",
            f"${row['Precio_Lista_Actual']:,.2f}",
            f"{coef_val:.2f}",
            f"{row['Oferta_Pct']:.1f}%",
            f"{margen_obj:.1f}%",
            f"${row['Nuevo_Precio_Sugerido']:,.2f}"
        ])
    t = Table(table_data, colWidths=[80, 65, 110, 70, 70, 65, 45, 65, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1d4ed8')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('FONTSIZE', (0,1), (-1,-1), 7),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

def generar_pdf_etiquetas(df_etiquetas: pd.DataFrame) -> bytes:
    if not HAS_REPORTLAB:
        return b""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    story = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('EtqTitle', parent=styles['Heading1'], fontSize=12, textColor=colors.HexColor('#1d4ed8'), alignment=1, spaceAfter=15)
    story.append(Paragraph("<b>ETIQUETAS DE GÓNDOLA (8x6 CM) - FARMACIA SOCIAL COPELCO</b>", title_style))
    story.append(Spacer(1, 10))
    estilo_etiqueta = ParagraphStyle('EstiloEtiqueta8x6', parent=styles['Normal'], alignment=1, leading=13)
    celdas_etiquetas = []
    path_logo_pdf = obtener_ruta_logo()
    for _, row in df_etiquetas.iterrows():
        prod_nombre = str(row['Producto'])
        codigo_prod = str(row.get('Codigo', ''))
        descuento_txt = f"{row['Oferta_Pct']:.0f}% OFF"
        precio_viejo = formato_pesos(row['Precio_Lista_Actual'])
        precio_nuevo = formato_pesos(row['Precio_Oferta_Publico'])
        elementos_celda = []
        if path_logo_pdf and os.path.exists(path_logo_pdf):
            try:
                img_logo = RLImage(path_logo_pdf, width=45, height=32)
                img_logo.hAlign = 'CENTER'
                elementos_celda.append(img_logo)
                elementos_celda.append(Spacer(1, 2))
            except Exception:
                pass
        linea_codigo = f"Cód: {codigo_prod}<br/>" if codigo_prod and codigo_prod != "-" else ""
        p_encabezado = Paragraph(f"<b><font color='#1d4ed8' size=7>FARMACIA SOCIAL COPELCO</font></b><br/>{linea_codigo}<b><font size=10 color='#0f172a'>{prod_nombre}</font></b>", estilo_etiqueta)
        elementos_celda.append(p_encabezado)
        elementos_celda.append(Spacer(1, 4))
        p_desc = Paragraph(f"<b><font color='#dc2626' size=20>{descuento_txt}</font></b>", ParagraphStyle('DescStyle', parent=styles['Normal'], alignment=1))
        t_desc_box = Table([[p_desc]], colWidths=[140], rowHeights=[36])
        t_desc_box.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fef2f2')),
            ('BOX', (0,0), (-1,-1), 2, colors.HexColor('#dc2626')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ]))
        elementos_celda.append(t_desc_box)
        elementos_celda.append(Spacer(1, 4))
        p_precios = Paragraph(f"<font color='#64748b' size=8>Precio Regular: <strike>{precio_viejo}</strike></font><br/><font color='#059669' size=12><b>Oferta: {precio_nuevo}</b></font>", estilo_etiqueta)
        elementos_celda.append(p_precios)
        t_individual = Table([[elementos_celda]], colWidths=[226], rowHeights=[165])
        t_individual.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#ffffff')),
            ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor('#1d4ed8')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        celdas_etiquetas.append(t_individual)
    filas_grid = []
    fila_actual = []
    for celda in celdas_etiquetas:
        fila_actual.append(celda)
        if len(fila_actual) == 2:
            filas_grid.append(fila_actual)
            fila_actual = []
    if fila_actual:
        while len(fila_actual) < 2:
            fila_actual.append("")
        filas_grid.append(fila_actual)
    if filas_grid:
        t_grid = Table(filas_grid, colWidths=[270, 270])
        t_grid.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 10),
            ('TOPPADDING', (0,0), (-1,-1), 10),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(t_grid)
    doc.build(story)
    buffer.seek(0)
    return buffer.read()

# ------------------------------------------------------------------
# LISTA DE RUBROS
# ------------------------------------------------------------------
LISTA_RUBROS = [
    "accesorios varios", "bazar", "bucales", "cosmetica", "dermatologia", 
    "herboristeria", "marroquineria", "nutricion deportiva", "ortopedia", "perfumeria/fragancias"
]

# ------------------------------------------------------------------
# BARRA LATERAL (LOGO AL TOPE Y CONFIGURACIÓN)
# ------------------------------------------------------------------
path_logo_activo = obtener_ruta_logo()
if path_logo_activo and os.path.exists(path_logo_activo):
    try:
        pil_logo = Image.open(path_logo_activo)
        st.sidebar.image(pil_logo, use_container_width=True)
    except Exception:
        pass

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configuración General")

if "coef_str" not in st.session_state:
    st.session_state.coef_str = "1.3"
if "iva_val" not in st.session_state:
    st.session_state.iva_val = 21.0

st.sidebar.markdown("**🔘 Coeficiente de Variación**")
col_m1, col_t1, col_p1 = st.sidebar.columns([1, 2.3, 1])
with col_m1:
    if st.button("➖", key="btn_coef_minus"):
        v = parsear_flotante(st.session_state.coef_str, default=1.3)
        st.session_state.coef_str = f"{max(1.0, v - 0.05):.2f}"
        st.rerun()
with col_p1:
    if st.button("➕", key="btn_coef_plus"):
        v = parsear_flotante(st.session_state.coef_str, default=1.3)
        st.session_state.coef_str = f"{v + 0.05:.2f}"
        st.rerun()
with col_t1:
    txt_c = st.text_input("coef_txt", value=st.session_state.coef_str, label_visibility="collapsed")
    st.session_state.coef_str = txt_c

coeficiente = float(str(st.session_state.coef_str).replace(",", ".")) if st.session_state.coef_str else 1.3

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
    txt_i = st.text_input("iva_txt", value=f"{st.session_state.iva_val:.1f}", label_visibility="collapsed")
    try:
        st.session_state.iva_val = float(txt_i.replace(",", "."))
    except ValueError:
        pass

iva_pct = st.session_state.iva_val

st.sidebar.markdown("---")
with st.sidebar.expander("🔒 Configuración Avanzada", expanded=False):
    logo_subido = st.file_uploader("Actualizar Logo Oficial", type=["png", "jpg", "jpeg"])
    if logo_subido is not None:
        try:
            img_temp = Image.open(logo_subido)
            img_temp.save(LOGO_OFICIAL)
            st.success("¡Logo actualizado con éxito!")
            st.rerun()
        except Exception as e:
            st.error(f"Error al guardar logo: {e}")

# ------------------------------------------------------------------
# ESTILOS CSS
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
    
    .etiqueta-gondola {
        border: 2px solid #1d4ed8;
        background-color: #ffffff;
        border-radius: 10px;
        padding: 18px;
        text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.08);
        margin-bottom: 15px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 190px;
    }
    .etq-farmacia {
        font-size: 0.75rem;
        text-transform: uppercase;
        color: #1d4ed8;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 3px;
    }
    .etq-codigo {
        font-size: 0.85rem;
        color: #475569;
        font-weight: 700;
        margin-bottom: 5px;
    }
    .etq-producto {
        font-size: 1.2rem;
        font-weight: 800;
        color: #0f172a;
        margin: 2px 0 6px 0;
        min-height: 42px;
    }
    .etq-descuento-box {
        background-color: #fef2f2;
        border: 2.5px solid #dc2626;
        color: #dc2626;
        font-size: 2.3rem;
        font-weight: 900;
        padding: 6px 18px;
        border-radius: 10px;
        display: inline-block;
        margin: 4px 0 8px 0;
        letter-spacing: 0.05em;
        box-shadow: 0 2px 6px rgba(220, 38, 38, 0.15);
    }
    .etq-bloque-precios {
        background-color: #f8fafc;
        border-radius: 6px;
        padding: 8px 12px;
        margin-top: 2px;
        border: 1px solid #e2e8f0;
        width: 100%;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .etq-precio-viejo {
        font-size: 0.95rem;
        color: #64748b;
        text-decoration: line-through;
        font-weight: 600;
    }
    .etq-precio-nuevo {
        font-size: 1.6rem;
        font-weight: 900;
        color: #059669;
    }

    div[data-testid="stButton"] button {
        width: 100%;
        padding: 6px 0px;
        font-weight: 700;
        font-size: 1.0rem;
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# VARIABLES MATEMÁTICAS GLOBALES
# ------------------------------------------------------------------
i = iva_pct / 100.0
margen_base_pct = (coeficiente - 1.0) * 100.0
descuento_quiebre_pct = ((coeficiente - 1.0) / coeficiente) * 100.0 if coeficiente > 0 else 0.0

# ------------------------------------------------------------------
# CABECERA: TÍTULO PRINCIPAL CON RECUADRO AZUL Y SÍMBOLO DÓLAR
# ------------------------------------------------------------------
st.markdown("""
<div style="border: 3px solid #1d4ed8; background-color: #f0f7ff; padding: 18px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 10px rgba(29,78,216,0.1);">
    <h1 style='color: #1e3a8a; font-size: 2.2rem; margin: 0; font-weight: 800;'>💰 Tablero de Precios, Ofertas y Rentabilidad</h1>
</div>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# PESTAÑAS
# ------------------------------------------------------------------
tab_simulador, tab_rubro, tab_auditoria = st.tabs([
    "⚡ Calculadora Unitaria por Etapas", 
    "📊 Ajuste Masivo por Rubro", 
    "📋 Auditoría y Reportes Gerenciales"
])

# ==================================================================
# PESTAÑA 1: CALCULADORA UNITARIA
# ==================================================================
with tab_simulador:
    st.subheader("1. Definición del Producto (Etapa 1)")
    
    col_e1_a, col_e1_b, col_e1_c = st.columns([1.5, 1, 1])
    with col_e1_a:
        prod_nombre = st.text_input("Descripción del Producto", value="", placeholder="Ej: Termo Keep Hammered")
    with col_e1_b:
        codigo_producto = st.text_input("Código de Barra / Sistema", value="", placeholder="Ej: 7791234567890")
    with col_e1_c:
        rubro_seleccionado = st.selectbox("Seleccioná el Segmento:", LISTA_RUBROS, key="rubro_unit", index=0)

    col_modo1, col_modo2 = st.columns(2)
    with col_modo1:
        modo_ingreso = st.radio(
            "¿Cómo tenés el dato del producto?",
            ["Ingresar Costo Sin IVA directamente", "Tengo el Precio de Lista Vigente (con IVA)"],
            horizontal=True,
            key="modo_ingreso_radio"
        )

    with col_modo2:
        if modo_ingreso == "Ingresar Costo Sin IVA directamente":
            costo_raw = st.text_input("Costo Sin IVA ($)", value="", placeholder="Ej: 36045,77", key="costo_unit_input")
            costo_sin_iva = parsear_monto(costo_raw)
        else:
            precio_lista_ingresado_raw = st.text_input("Precio de Lista Vigente en Sistema (con IVA) ($)", value="", placeholder="Ej: 56700,00", key="precio_lista_input")
            precio_lista_ingresado = parsear_monto(precio_lista_ingresado_raw)
            if coeficiente > 0 and (1 + i) > 0 and precio_lista_ingresado > 0:
                costo_sin_iva = precio_lista_ingresado / ((1 + i) * coeficiente)
            else:
                costo_sin_iva = 0.0
            if precio_lista_ingresado > 0:
                st.success(f"🔍 **Costo deducido automáticamente:** **{formato_pesos(costo_sin_iva)}**")

    precio_actual_lista_con_iva = (costo_sin_iva * coeficiente) * (1 + i)

    st.markdown("---")
    st.subheader("2. Estrategia de Oferta y Rentabilidad Objetivo (Etapa 2)")
    
    col_e2_1, col_e2_2 = st.columns(2)
    with col_e2_1:
        descuento_oferta_pct = st.number_input(
            "🏷️ Oferta / Descuento a realizar (%)",
            min_value=0.0, max_value=90.0, value=15.0, step=1.0, key="num_desc_oferta"
        )
    with col_e2_2:
        margen_mantener_pct = st.number_input(
            "🛡️ Rentabilidad Post-Oferta a MANTENER s/costo (%)",
            min_value=0.0, max_value=200.0, value=25.0, step=1.0, key="num_margen_mant"
        )

    d = descuento_oferta_pct / 100.0
    m_objetivo = margen_mantener_pct / 100.0
    
    precio_lista_nuevo_con_iva = (costo_sin_iva * (1 + m_objetivo) * (1 + i)) / (1 - d) if (1 - d) > 0 else 0
    diferencia_dinero = precio_lista_nuevo_con_iva - precio_actual_lista_con_iva
    porcentaje_aumento = ((precio_lista_nuevo_con_iva / precio_actual_lista_con_iva) - 1) * 100 if precio_actual_lista_con_iva > 0 else 0
    precio_mostrador_oferta = precio_lista_nuevo_con_iva * (1 - d)

    margen_sin_remarcar_pct = (coeficiente * (1.0 - d) - 1.0) * 100.0
    esta_en_perdida = descuento_oferta_pct > descuento_quiebre_pct
    exceso_descuento_pct = max(0.0, descuento_oferta_pct - descuento_quiebre_pct)

    st.markdown("#### 📌 Parámetros de Interés Actuales")
    es_saludable = (margen_mantener_pct >= 10.0) and (margen_sin_remarcar_pct >= 0.0)
    color_margen = "bg-green" if es_saludable else "bg-red"
    icono_margen = "🟢" if es_saludable else "🔴"
    estado_texto = "Saludable" if es_saludable else "⚠️ En Riesgo / Pérdida"
    color_quiebre = "bg-red" if esta_en_perdida else "bg-amber"
    sub_quiebre = f"🚨 Superado por +{exceso_descuento_pct:.2f}%" if esta_en_perdida else "Descuento máx. sin perder"

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-container bg-blue">
            <div class="kpi-title">🏷️ Descuento Configurado</div>
            <div class="kpi-value">{descuento_oferta_pct:.1f}%</div>
            <div class="kpi-sub">Promoción en mostrador</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-container {color_margen}">
            <div class="kpi-title">{icono_margen} Margen Post-Oferta</div>
            <div class="kpi-value">{margen_mantener_pct:.1f}%</div>
            <div class="kpi-sub">{estado_texto}</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-container {color_quiebre}">
            <div class="kpi-title">🚨 Umbral de Pérdida</div>
            <div class="kpi-value">{descuento_quiebre_pct:.2f}%</div>
            <div class="kpi-sub">{sub_quiebre}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-container bg-purple">
            <div class="kpi-title">🔘 Coef. de Variación</div>
            <div class="kpi-value">{coeficiente}</div>
            <div class="kpi-sub">Rentabilidad base: +{margen_base_pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("3. Resultados de Remarcación y Análisis Financiero")

    c_res1, c_res2 = st.columns(2)
    c_res1.metric("📈 Porcentaje a Aumentar en Lista", f"{porcentaje_aumento:+.2f}%".replace(".", ","), delta_color="inverse")
    c_res2.metric("💵 Dinero a Aumentar (por unidad)", formato_pesos(diferencia_dinero), delta_color="inverse")

    st.markdown("---")
    c_pl1, c_pl2 = st.columns(2)
    c_pl1.write(f"**Precio de Lista Actual:**\n### {formato_pesos(precio_actual_lista_con_iva)}")
    c_pl2.write(f"**NUEVO Precio de Lista Sugerido:**\n<h2 style='color:#059669; margin:0;'>{formato_pesos(precio_lista_nuevo_con_iva)}</h2>", unsafe_allow_html=True)

    st.markdown("---")
    precio_neto_sin_iva = precio_mostrador_oferta / (1 + i)
    ganancia_neta_pesos = precio_neto_sin_iva - costo_sin_iva
    margen_efectivo_real = (ganancia_neta_pesos / costo_sin_iva) * 100 if costo_sin_iva > 0 else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Precio Final en Caja con Oferta", formato_pesos(precio_mostrador_oferta))
    m2.metric("Ganancia Neta Unitaria", formato_pesos(ganancia_neta_pesos))
    m3.metric("Rentabilidad Asegurada", f"{margen_efectivo_real:.2f}%".replace(".", ","))

    st.markdown("---")
    
    if st.button("💾 Guardar este Producto y Simulación en Auditoría", type="primary", use_container_width=True):
        if not prod_nombre.strip():
            st.warning("⚠️ Por favor, ingresá una descripción para el producto antes de guardar.")
        else:
            ahora = datetime.now()
            registro = {
                "ID": ahora.strftime("%Y%m%d%H%M%S%f"),
                "Fecha_Hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                "Rubro": rubro_seleccionado,
                "Codigo": codigo_producto if codigo_producto.strip() else "-",
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
            st.success(f"✅ ¡Guardado con éxito para auditoría! El producto **'{prod_nombre}'** (Cód: {registro['Codigo']}) fue registrado correctamente.")


# ==================================================================
# PESTAÑA 2: AJUSTE MASIVO POR RUBRO
# ==================================================================
with tab_rubro:
    st.subheader("📊 Simulación y Ajuste Global por Segmento mediante Costo Medio")
    col_r1, col_r2 = st.columns([1, 1.2])

    with col_r1:
        rubro_masivo = st.selectbox("Seleccioná el Segmento a Ajustar:", LISTA_RUBROS, key="rubro_masivo_sel")
        costo_medio_raw = st.text_input("Costo Medio / Promedio del Segmento sin IVA ($)", value="", placeholder="Ej: 15000,00", key="costo_medio_input")
        costo_medio = parsear_monto(costo_medio_raw)
        
        desc_masivo = st.number_input("Descuento de Oferta para el Segmento (%)", min_value=0.0, max_value=90.0, value=15.0, key="d_masivo")
        margen_masivo = st.number_input("Rentabilidad Post-Oferta para el Segmento (%)", min_value=0.0, max_value=200.0, value=25.0, key="m_masivo")

        d_m = desc_masivo / 100.0
        m_m = margen_masivo / 100.0

        precio_actual_medio_iva = (costo_medio * coeficiente) * (1 + i)
        precio_sugerido_medio_iva = (costo_medio * (1 + m_m) * (1 + i)) / (1 - d_m) if (1 - d_m) > 0 else 0
        aumento_dinero_medio = precio_sugerido_medio_iva - precio_actual_medio_iva
        aumento_pct_medio = ((precio_sugerido_medio_iva / precio_actual_medio_iva) - 1) * 100 if precio_actual_medio_iva > 0 else 0
        precio_oferta_medio = precio_sugerido_medio_iva * (1 - d_m)

        st.markdown("---")
        if st.button("💾 Guardar Referencia Global de Segmento", use_container_width=True):
            if costo_medio <= 0:
                st.warning("⚠️ Por favor, ingresá un costo medio válido.")
            else:
                ahora = datetime.now()
                registro_rubro = {
                    "ID": ahora.strftime("%Y%m%d%H%M%S%f"),
                    "Fecha_Hora": ahora.strftime("%Y-%m-%d %H:%M:%S"),
                    "Rubro": rubro_masivo,
                    "Codigo": "GLOBAL",
                    "Producto": f"[SEGMENTO GLOBAL - Costo Medio: {formato_pesos(costo_medio)}]",
                    "Costo_Sin_IVA": round(costo_medio, 2),
                    "Coeficiente": round(coeficiente, 4),
                    "Oferta_Pct": round(desc_masivo, 2),
                    "Margen_Objetivo_Pct": round(margen_masivo, 2),
                    "Precio_Lista_Actual": round(precio_actual_medio_iva, 2),
                    "Nuevo_Precio_Sugerido": round(precio_sugerido_medio_iva, 2),
                    "Aumento_Pct": round(aumento_pct_medio, 2),
                    "Aumento_Dinero": round(aumento_dinero_medio, 2),
                    "Precio_Oferta_Publico": round(precio_oferta_medio, 2)
                }
                guardar_registro(registro_rubro)
                st.success(f"✅ ¡Guardado con éxito para auditoría! Parámetros globales registrados para el segmento **{rubro_masivo}**.")

    with col_r2:
        st.markdown(f"### 📈 Impacto del Ajuste: *{rubro_masivo.upper()}*")
        m_col1, m_col2 = st.columns(2)
        m_col1.metric("Aumento Sugerido", f"{aumento_pct_medio:+.2f}%".replace(".", ","), delta_color="inverse")
        m_col2.metric("Aumento en Dinero", formato_pesos(aumento_dinero_medio), delta_color="inverse")
        st.markdown("---")
        r_pl1, r_pl2 = st.columns(2)
        r_pl1.write(f"**Precio Actual:**\n### {formato_pesos(precio_actual_medio_iva)}")
        r_pl2.write(f"**NUEVO Precio Sugerido:**\n<h2 style='color:#059669; margin:0;'>{formato_pesos(precio_sugerido_medio_iva)}</h2>", unsafe_allow_html=True)


# ==================================================================
# PESTAÑA 3: AUDITORÍA, CONTEO Y ETIQUETAS DE GÓNDOLA
# ==================================================================
with tab_auditoria:
    st.subheader("📋 Dashboard Gerencial, Conteo Diario y Etiquetas de Góndola")
    
    col_lim1, _ = st.columns([1, 2])
    with col_lim1:
        if st.button("🗑️ Limpiar y Vaciar Historial Completo", type="secondary"):
            vaciar_historial_completo()
            st.success("¡Historial y respaldo vaciados con éxito!")
            st.rerun()

    df_hist = cargar_historial()

    if df_hist.empty:
        st.info("ℹ️ Todavía no hay registros de ofertas guardados en la base de datos.")
    else:
        st.markdown("#### 📅 Resumen: Cantidad de Registros Guardados por Día y Segmento")
        df_hist["Solo_Fecha"] = pd.to_datetime(df_hist["Fecha_Hora"]).dt.date
        df_conteo = df_hist.groupby(["Solo_Fecha", "Rubro"]).agg(
            Cantidad_Registros=("Producto", "count")
        ).reset_index()
        df_conteo["Fecha"] = df_conteo["Solo_Fecha"].astype(str)
        df_conteo["Segmento"] = df_conteo["Rubro"].str.title()
        df_conteo = df_conteo[["Fecha", "Segmento", "Cantidad_Registros"]].sort_values(by=["Fecha", "Segmento"], ascending=[False, True])
        st.dataframe(df_conteo, use_container_width=True, hide_index=True)
        st.markdown("---")

        col_f1, col_f2, col_f3 = st.columns([1.5, 1.5, 2])
        fechas_disponibles = pd.to_datetime(df_hist["Fecha_Hora"]).dt.date
        fecha_min = fechas_disponibles.min()
        fecha_max = fechas_disponibles.max()

        with col_f1:
            f_desde = st.date_input("Fecha Desde (Histórico):", value=fecha_min, min_value=fecha_min, max_value=date.today(), key="f_d_aud")
        with col_f2:
            f_hasta = st.date_input("Fecha Hasta (Histórico):", value=fecha_max, min_value=fecha_min, max_value=date.today(), key="f_h_aud")
        with col_f3:
            rubro_filtro = st.selectbox("Filtrar por Segmento:", ["Todos los segmentos"] + LISTA_RUBROS, key="r_f_aud")

        mask = (df_hist["Fecha_DT"] >= f_desde) & (df_hist["Fecha_DT"] <= f_hasta)
        if rubro_filtro != "Todos los segmentos":
            mask = mask & (df_hist["Rubro"] == rubro_filtro)
        
        df_filtrado = df_hist[mask].copy()

        st.markdown("---")
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("Registros en Periodo", len(df_filtrado))
        aum_prom = df_filtrado["Aumento_Pct"].mean() if not df_filtrado.empty else 0.0
        aum_max = df_filtrado["Aumento_Pct"].max() if not df_filtrado.empty else 0.0
        rubro_top = df_filtrado["Rubro"].mode()[0] if not df_filtrado.empty else "-"

        a2.metric("Remarcación Promedio", f"{aum_prom:+.2f}%".replace(".", ","))
        a3.metric("Remarcación Máxima", f"{aum_max:+.2f}%".replace(".", ","))
        a4.metric("Segmento Más Activo", rubro_top)

        st.markdown("---")

        if not df_filtrado.empty:
            st.markdown("#### 🏷️ Selección de Productos para Etiquetas de Góndola (8x6 cm)")
            st.caption("Tildá los productos uno a uno o utilizá el botón general para seleccionarlos todos de golpe.")

            if "select_all_state" not in st.session_state:
                st.session_state.select_all_state = False

            col_btn_all, col_info_sel = st.columns([2.5, 3])
            with col_btn_all:
                texto_btn_todos = "☑️ Seleccionar Todos los Registros" if not st.session_state.select_all_state else "◻️ Deseleccionar Todos"
                if st.button(texto_btn_todos, use_container_width=True):
                    st.session_state.select_all_state = not st.session_state.select_all_state
                    for r_id in df_filtrado['ID'].astype(str):
                        st.session_state[f"chk_{r_id}"] = st.session_state.select_all_state
                    st.rerun()

            ids_seleccionados = []
            for idx, row in df_filtrado.iterrows():
                r_id_str = str(row['ID'])
                if f"chk_{r_id_str}" not in st.session_state:
                    st.session_state[f"chk_{r_id_str}"] = st.session_state.select_all_state

                c_chk, c_info1, c_info2, c_info3, c_btn = st.columns([0.6, 2.5, 3, 3, 1])
                
                sel = c_chk.checkbox("Seleccionar", key=f"chk_{r_id_str}", label_visibility="collapsed")
                if sel:
                    ids_seleccionados.append(row['ID'])

                coef_v = float(row['Coeficiente'])
                obj_v = float(row['Margen_Objetivo_Pct'])
                cod_val = row.get('Codigo', '-')

                c_info1.write(f"**[{str(row['Rubro']).title()}]**\n\nCód: {cod_val}")
                c_info2.write(f"📦 {row['Producto']}\n\nCosto: {formato_pesos(row['Costo_Sin_IVA'])}")
                c_info3.write(f"Oferta: {row['Oferta_Pct']:.1f}% | Post: {obj_v:.1f}% | Nuevo: {formato_pesos(row['Precio_Oferta_Publico'])}")
                
                with c_btn:
                    if st.button("🗑️", key=f"del_{row['ID']}", help="Eliminar este registro permanentemente"):
                        eliminar_registro_por_id(row['ID'])
                        st.rerun()
                st.markdown("<hr style='margin:5px 0px; opacity:0.3;'>", unsafe_allow_html=True)

            # ------------------------------------------------------------------
            # VISTA PREVIA Y DESCARGA EN PDF (GRILLA 2 COLUMNAS 8x6 CM)
            # ------------------------------------------------------------------
            if ids_seleccionados:
                st.markdown("---")
                st.markdown(f"### 🖨️ Vista Previa de Etiquetas ({len(ids_seleccionados)} seleccionados)")

                df_etiquetas = df_filtrado[df_filtrado["ID"].isin(ids_seleccionados)]

                if HAS_REPORTLAB:
                    pdf_etq_bytes = generar_pdf_etiquetas(df_etiquetas)
                    st.download_button(
                        label="🖨️ Descargar Etiquetas 8x6 cm en Grilla (2 Columnas) para Imprimir",
                        data=pdf_etq_bytes,
                        file_name=f"etiquetas_gondola_8x6_copelco.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        type="primary"
                    )

                cols_etq = st.columns(2)
                for idx_e, (_, row_e) in enumerate(df_etiquetas.iterrows()):
                    col_target = cols_etq[idx_e % 2]
                    
                    cod_e = row_e.get('Codigo', '')
                    precio_viejo = formato_pesos(row_e['Precio_Lista_Actual'])
                    precio_nuevo = formato_pesos(row_e['Precio_Oferta_Publico'])
                    descuento_txt = f"{row_e['Oferta_Pct']:.0f}% OFF"
                    
                    with col_target:
                        st.markdown(f"""
                        <div class="etiqueta-gondola">
                            <div class="etq-farmacia">FARMACIA SOCIAL COPELCO</div>
                            <div class="etq-codigo">Cód: {cod_e}</div>
                            <div class="etq-producto">{row_e['Producto']}</div>
                            <div><span class="etq-descuento-box"><b>{descuento_txt}</b></span></div>
                            <div class="etq-bloque-precios">
                                <span class="etq-precio-viejo">Precio Regular: {precio_viejo}</span>
                                <span class="etq-precio-nuevo"><b>Oferta: {precio_nuevo}</b></span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("##### 📥 Exportación de Informes y Respaldo Definitivo")

            col_exp1, col_exp2, col_exp3 = st.columns(3)

            with col_exp1:
                df_exp = pd.DataFrame()
                df_exp["Segmento"] = df_filtrado["Rubro"].str.title()
                df_exp["Código"] = df_filtrado.get("Codigo", "-")
                df_exp["Producto"] = df_filtrado["Producto"]
                df_exp["Precio Costo"] = df_filtrado["Costo_Sin_IVA"].apply(formato_pesos)
                df_exp["Precio de Lista"] = df_filtrado["Precio_Lista_Actual"].apply(formato_pesos)
                df_exp["Rentabilidad"] = df_filtrado["Coeficiente"].apply(lambda c: f"{c:.2f} ({(c-1)*100:.0f}%)")
                df_exp["Oferta"] = df_filtrado["Oferta_Pct"].apply(lambda x: f"{x:.1f}%")
                df_exp["Rentabilidad Post-Oferta"] = df_filtrado["Margen_Objetivo_Pct"].apply(lambda x: f"{x:.1f}%")
                df_exp["Rentabilidad Cedida"] = df_filtrado.apply(lambda r: f"{max(0.0, (float(r['Coeficiente'])-1)*100 - float(r['Margen_Objetivo_Pct'])):.1f}%", axis=1)
                df_exp["Nuevo Precio de Lista"] = df_filtrado["Nuevo_Precio_Sugerido"].apply(formato_pesos)

                csv_export = df_exp.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📊 Descargar Informe Excel / CSV",
                    data=csv_export,
                    file_name=f"informe_ofertas_{f_desde}_al_{f_hasta}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col_exp2:
                if HAS_REPORTLAB:
                    pdf_bytes = generar_pdf_auditoria(df_filtrado, f_desde, f_hasta)
                    st.download_button(
                        label="📑 Descargar Informe PDF Formal",
                        data=pdf_bytes,
                        file_name=f"informe_ofertas_{f_desde}_al_{f_hasta}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.button("📑 PDF (Instalar ReportLab)", disabled=True, use_container_width=True)

            with col_exp3:
                db_completa_bytes = df_hist.drop(columns=["Fecha_DT", "Solo_Fecha"], errors="ignore").to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="💾 Copia de Seguridad Base Datos",
                    data=db_completa_bytes,
                    file_name="respaldo_total_historial_ofertas.csv",
                    mime="text/csv",
                    help="Guarda en tu computadora el historial completo de todas las fechas",
                    use_container_width=True
                )
        else:
            st.warning("No hay registros en el rango de fechas o segmento seleccionado.")
