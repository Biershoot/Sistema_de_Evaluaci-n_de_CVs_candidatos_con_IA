"""Interfaz Streamlit: cliente de la misma lógica que expone la API."""

import streamlit as st

from app.config import get_settings
from app.exceptions import ConfigurationError, EvaluationError, PDFExtractionError
from app.models.cv_model import AnalisisCV, NivelAjuste
from app.services.cv_evaluator import evaluar_candidato
from app.services.pdf_processor import extraer_texto_pdf

# Estilo visual por banda de ajuste. Los umbrales viven en AnalisisCV, así que
# la UI solo decide cómo pintar cada nivel, no dónde están los cortes.
_ESTILO_NIVEL: dict[NivelAjuste, tuple[str, str, str]] = {
    NivelAjuste.EXCELENTE: ("🟢", "EXCELENTE", "Candidato altamente recomendado"),
    NivelAjuste.BUENO: ("🟡", "BUENO", "Candidato recomendado con reservas"),
    NivelAjuste.REGULAR: ("🟠", "REGULAR", "Candidato requiere evaluación adicional"),
    NivelAjuste.BAJO: ("🔴", "BAJO", "Candidato no recomendado"),
}

_PLACEHOLDER_PUESTO = """Ejemplo:

**Puesto:** Desarrollador Frontend Senior

**Requisitos obligatorios:**
- 3+ años de experiencia en desarrollo frontend
- Dominio de React.js y JavaScript/TypeScript
- Experiencia con HTML5, CSS3 y frameworks CSS (Bootstrap, Tailwind)

**Requisitos deseables:**
- Experiencia con Next.js
- Conocimientos de testing (Jest, Cypress)

**Responsabilidades:**
- Desarrollo de interfaces responsivas
- Colaboración con equipos de diseño y backend"""


def main() -> None:
    """Punto de entrada de la interfaz."""
    st.set_page_config(
        page_title="Sistema de Evaluación de CVs",
        page_icon="📄",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.title("📄 Sistema de Evaluación de CVs con IA")
    st.markdown(
        "**Analiza currículums y evalúa candidatos de forma objetiva usando IA.** "
        "Extrae información del PDF, la contrasta con el puesto y devuelve un "
        "análisis estructurado con porcentaje de ajuste."
    )

    if not get_settings().is_configured:
        st.error(
            "⚠️ Falta `OPENAI_API_KEY`. Crea un fichero `.env` a partir de "
            "`.env.example` antes de analizar CVs."
        )

    st.divider()

    col_entrada, col_resultado = st.columns([1, 1], gap="large")
    with col_entrada:
        _procesar_entrada()
    with col_resultado:
        _mostrar_area_resultados()


def _procesar_entrada() -> None:
    """Recoge el CV y la descripción del puesto."""
    st.header("📋 Datos de Entrada")

    archivo_cv = st.file_uploader(
        "**1. Sube el CV del candidato (PDF)**",
        type=["pdf"],
        help="El texto debe ser seleccionable; los CVs escaneados como imagen "
        "no se pueden leer.",
    )

    if archivo_cv is not None:
        st.success(f"✅ Archivo cargado: {archivo_cv.name}")
        st.caption(f"📊 Tamaño: {archivo_cv.size:,} bytes")

    st.markdown("**2. Descripción del puesto de trabajo**")
    descripcion_puesto = st.text_area(
        "Detalla los requisitos, responsabilidades y habilidades necesarias:",
        height=250,
        placeholder=_PLACEHOLDER_PUESTO,
        help="Cuanto más específica sea la descripción, más ajustada será la evaluación.",
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        analizar = st.button(
            "🔍 Analizar Candidato", type="primary", use_container_width=True
        )
    with col_btn2:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.session_state["archivo_cv"] = archivo_cv
    st.session_state["descripcion_puesto"] = descripcion_puesto
    st.session_state["analizar"] = analizar


def _mostrar_area_resultados() -> None:
    """Valida la entrada y lanza el análisis."""
    st.header("📊 Resultado del Análisis")

    if not st.session_state.get("analizar", False):
        st.info(
            "👆 **Instrucciones:**\n\n"
            "1. Sube un CV en PDF en la columna izquierda\n"
            "2. Describe detalladamente el puesto\n"
            '3. Pulsa "Analizar Candidato"\n\n'
            "**Consejos:** usa CVs con texto seleccionable e incluye "
            "requisitos obligatorios y deseables."
        )
        return

    archivo_cv = st.session_state.get("archivo_cv")
    descripcion_puesto = (st.session_state.get("descripcion_puesto") or "").strip()

    if archivo_cv is None:
        st.error("⚠️ Sube un archivo PDF con el currículum.")
        return
    if not descripcion_puesto:
        st.error("⚠️ Proporciona una descripción del puesto.")
        return

    _procesar_analisis(archivo_cv, descripcion_puesto)


def _procesar_analisis(archivo_cv, descripcion_puesto: str) -> None:
    """Ejecuta el pipeline completo y muestra el resultado o el error."""
    settings = get_settings()

    try:
        with st.spinner("📄 Extrayendo texto del PDF..."):
            texto_cv = extraer_texto_pdf(
                archivo_cv.getvalue(), max_chars=settings.max_cv_chars
            )

        with st.spinner("🤖 Analizando candidato con IA..."):
            resultado = evaluar_candidato(texto_cv, descripcion_puesto)

    except PDFExtractionError as exc:
        st.error(f"❌ No se pudo leer el PDF: {exc}")
        return
    except ConfigurationError as exc:
        st.error(f"⚙️ Configuración incompleta: {exc}")
        return
    except EvaluationError as exc:
        st.error(f"🤖 El análisis falló: {exc}")
        st.caption(
            "Reintenta en unos segundos; puede ser un fallo temporal del proveedor."
        )
        return
    except ValueError as exc:
        st.error(f"⚠️ Entrada inválida: {exc}")
        return

    _mostrar_resultados(resultado)


def _mostrar_resultados(resultado: AnalisisCV) -> None:
    """Pinta el análisis de forma estructurada."""
    color, nivel, mensaje = _ESTILO_NIVEL[resultado.nivel_ajuste]

    st.subheader("🎯 Evaluación Principal")
    st.metric(
        label="Porcentaje de Ajuste al Puesto",
        value=f"{resultado.porcentaje_ajuste}%",
        delta=f"{color} {nivel}",
        delta_color="off",
    )
    st.progress(resultado.porcentaje_ajuste / 100)
    st.markdown(f"**{mensaje}**")

    st.divider()

    st.subheader("👤 Perfil del Candidato")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**👨‍💼 Nombre:** {resultado.nombre_candidato}")
        st.info(f"**⏱️ Experiencia:** {resultado.experiencia_anios} años")
    with col2:
        st.info(f"**🎓 Educación:** {resultado.educacion}")

    st.subheader("💼 Experiencia Relevante")
    st.info(resultado.experiencia_relevante)

    st.divider()

    st.subheader("🛠️ Habilidades Clave")
    if resultado.habilidades_clave:
        columnas = st.columns(min(len(resultado.habilidades_clave), 4))
        for i, habilidad in enumerate(resultado.habilidades_clave):
            with columnas[i % len(columnas)]:
                st.success(f"✅ {habilidad}")
    else:
        st.warning("No se identificaron habilidades específicas.")

    st.divider()

    col_fortalezas, col_mejoras = st.columns(2)
    with col_fortalezas:
        st.subheader("💪 Fortalezas")
        for i, fortaleza in enumerate(resultado.fortalezas, 1):
            st.markdown(f"**{i}.** {fortaleza}")
    with col_mejoras:
        st.subheader("📈 Áreas de Desarrollo")
        for i, area in enumerate(resultado.areas_mejora, 1):
            st.markdown(f"**{i}.** {area}")

    st.divider()

    st.subheader("📋 Recomendación Final")
    if resultado.recomendado:
        st.success(
            "✅ **CANDIDATO RECOMENDADO**\n\n"
            "El perfil está alineado con los requisitos. Se recomienda avanzar "
            "a la siguiente fase del proceso."
        )
    elif resultado.porcentaje_ajuste >= 50:
        st.warning(
            "⚠️ **CANDIDATO CON POTENCIAL**\n\n"
            "Requiere evaluación adicional. Se recomienda una entrevista técnica "
            "para validar competencias."
        )
    else:
        st.error(
            "❌ **CANDIDATO NO RECOMENDADO**\n\n"
            "El perfil no se alinea suficientemente con los requisitos del puesto."
        )

    st.divider()
    st.download_button(
        "💾 Descargar análisis (JSON)",
        data=resultado.model_dump_json(indent=2),
        file_name=f"analisis_{resultado.nombre_candidato.replace(' ', '_').lower()}.json",
        mime="application/json",
        use_container_width=True,
    )
