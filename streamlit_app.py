"""Punto de entrada de la interfaz Streamlit.

Uso: streamlit run streamlit_app.py
"""

from app.config import get_settings
from app.logging_config import setup_logging
from ui.streamlit_ui import main

if __name__ == "__main__":
    setup_logging(get_settings().log_level)
    main()
