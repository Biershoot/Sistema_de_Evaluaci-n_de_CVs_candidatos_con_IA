"""Excepciones del dominio.

Cada excepción representa un modo de fallo que la capa de API sabe traducir a un
código HTTP concreto (ver `app.api.main`). Las capas internas nunca devuelven
strings ni objetos "de error": lanzan una de estas.
"""


class CVAnalyzerError(Exception):
    """Base de todos los errores del dominio."""


class PDFExtractionError(CVAnalyzerError):
    """El PDF no se pudo leer o no contiene texto extraíble.

    Causas típicas: fichero corrupto, PDF cifrado, o un CV escaneado como
    imagen sin capa de texto (requeriría OCR).
    """


class EvaluationError(CVAnalyzerError):
    """El modelo no pudo producir una evaluación válida.

    Cubre fallos de red, límites de cuota y respuestas que no encajan en el
    esquema `AnalisisCV`.
    """


class ConfigurationError(CVAnalyzerError):
    """Falta configuración obligatoria para arrancar el servicio."""
