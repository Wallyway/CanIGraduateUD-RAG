import re
import time
import ipaddress
import threading
import unicodedata
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
try:
    from fastapi import Request, HTTPException, status
except ImportError:
    Request = Any
    HTTPException = Exception
    status = Any

try:
    from sqlalchemy.orm import Session
except ImportError:
    Session = Any

import logging

logger = logging.getLogger(__name__)

# Maximum query length in characters to prevent token exhaustion DoS
MAX_QUERY_LENGTH = 1500

# 24 Hours in seconds
PENALTY_DURATION_SECONDS = 24 * 3600

# Strict Strike Threshold
MAX_STRIKES = 3


def normalize_text(text: str) -> str:
    """
    Normalizes text by removing accents, diacritics, and converting to lowercase
    for robust, accent-agnostic keyword matching and pattern detection.
    """
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in normalized if not unicodedata.combining(c))
    return stripped.lower().strip()


# ==============================================================================
# 1. REGEX PATTERNS FOR CYBERATTACKS & ABUSE GATES
# ==============================================================================

# Prompt Injection, Jailbreaks & System Prompt Leakage
PROMPT_INJECTION_PATTERNS = [
    # Instruction overrides & role abandonment
    r"(?i)\b(?:ignore|ignora|desestima|olvida|bypass|salta|descarta)\b.*?\b(?:previous|anteriores|instructions|instrucciones|directrices|reglas|rules|mandatos|normas)\b",
    r"(?i)\b(?:nueva\s+regla|new\s+rule|system\s+override|anula\s+tus\s+instrucciones|olvida\s+tu\s+rol|cambia\s+de\s+rol)\b",
    r"(?i)\b(?:olvida\s+todo|deshazte\s+de\s+tus\s+instrucciones|haz\s+caso\s+omiso)\b",
    
    # System prompt extraction & leakage
    r"(?i)\b(?:system\s*prompt|prompt\s*del\s*sistema|instrucciones\s*secretas|developer\s*mode|modo\s*desarrollador|jailbreak|dan\s*mode)\b",
    r"(?i)\b(?:repite\s+(?:exactamente\s+)?(?:el\s+texto\s+anterior|tus\s+instrucciones|tu\s+prompt)|muestra\s+tu\s+prompt|revela\s+tus\s+instrucciones|cu[aá]l\s+es\s+tu\s+system\s+prompt)\b",
    r"(?i)\b(?:what\s+is\s+your\s+system\s+prompt|repeat\s+(?:all\s+)?instructions\s+above|print\s+initial\s+prompt)\b",
    
    # DAN, Jailbreaks & Unrestricted Persona
    r"(?i)\b(?:dan|do\s+anything\s+now)\b.*?\b(?:unrestricted|sin\s+restricciones|sin\s+filtros|bypass|filters\s+disabled|disabled\s+by\s+the\s+developers)\b",
    r"(?i)\b(?:act[uú]a\s+como|pretend\s+to\s+be|roleplay\s+as|you\s+are\s+now)\b.*?\b(?:sin\s+restricciones|unrestricted|hacker|inmoral|ilegal|jailbreak|sin\s+censura|dan)\b",
    
    # Delimiter and raw prompt injection tokens
    r"(?:<\|im_start\|>|<\|im_end\|>|\[SYSTEM\]|\[INST\]|###\s*System|```\s*system|Assistant:\s*understood)",
    
    # Obfuscation & decoding injection attempts
    r"(?i)\b(?:decode\s+this\s+base64|decodifica\s+(?:este\s+)?base64|ejecuta\s+(?:este\s+)?base64|rot13|cifrado\s+cesar)\b.*?\b(?:and\s+execute|y\s+ejecuta|instrucciones)\b",
]

# Completely Non-Academic / Abuse Patterns (Zero-Token Fast Gate)
ABUSE_AND_OFFTOPIC_PATTERNS = [
    # Explicit examples from specifications:
    # 1. "Cuentame un cuento" / Historias / Canciones / Poemas / Chistes
    (r"(?i)\b(?:cu[eé]ntame\s+(?:un\s+)?cuento|dime\s+un\s+cuento|narra\s+(?:un\s+)?cuento|escribe\s+(?:un\s+)?cuento|invento?\s+un\s+cuento|cu[eé]ntame\s+una\s+historia|narra\s+una\s+historia|cuento\s+de\s+hadas|f[aá]bula)\b",
     "Petición de cuentos o narraciones fantásticas no académicas"),
    
    # 2. "Hablame en chino" / Idiomas arbitrarios ajenos al ámbito universitario
    (r"(?i)\b(?:h[aá]blame\s+en\s+(?:chino|japon[eé]s|ruso|mandar[ií]n|alem[aá]n|coreano|italiano|portugu[eé]s|franc[eé]s|lat[ií]n)|responde\s+en\s+(?:chino|japon[eé]s|ruso|mandar[ií]n|alem[aá]n|coreano|italiano|portugu[eé]s|franc[eé]s)|traduce\s+(?:al|en)\s+(?:chino|japon[eé]s|ruso|mandar[ií]n|alem[aá]n|coreano|italiano|portugu[eé]s|franc[eé]s))\b",
     "Petición de conversación en lenguas ajenas a la temática de grado"),
     
    # 3. "Necesito novia" / Romance / Citas / Búsqueda de pareja
    (r"(?i)\b(?:necesito\s+novi[ao]|quiero\s+novi[ao]|busco\s+novi[ao]|cons[ií]gueme\s+novi[ao]|tienes\s+novi[ao]|quieres\s+ser\s+mi\s+novi[ao]|eres\s+(?:mi\s+)?amor|te\s+amo|estoy\s+sol[ao]\s+y\s+triste|dame\s+cari[ñn]o|dame\s+un\s+beso|b[eé]same)\b",
     "Contenido de romance, citas o peticiones personales ajenas a la universidad"),

    # Chistes, poemas y entretenimiento general
    (r"(?i)\b(?:cu[eé]ntame\s+un\s+chiste|dime\s+un\s+chiste|hazme\s+re[ií]r|escribe\s+(?:un\s+)?poema|canta\s+(?:una\s+)?canci[oó]n|hazme\s+una\s+rima|adivinanza|recomi[eé]ndame\s+una\s+pel[ií]cula)\b",
     "Petición de entretenimiento, chistes o poemas fuera del ámbito de grados"),

    # Gastronomía, cocina, recetas
    (r"(?i)\b(?:receta\s+de|c[oó]mo\s+(?:se\s+)?hace\s+(?:una\s+)?pizza|ingredientes\s+para\s+cocinar|c[oó]mo\s+preparar\s+(?:arroz|comida|pollo|torta|postre|pizza|sushi|pasta|tacos))\b",
     "Consultas de cocina y gastronomía ajenas a la universidad"),

    # Deportes y apuestas generales
    (r"(?i)\b(?:qui[eé]n\s+gan[oó]\s+el\s+partido|resultado\s+del\s+partido|champions\s+league|n[uú]meros\s+de\s+la\s+loter[ií]a|dame\s+el\s+baloto|pron[oó]stico\s+de\s+f[uú]tbol|apuesta\s+deportiva)\b",
     "Consultas deportivas o de azar no relacionadas"),

    # Creación de malware y cibercrimen
    (r"(?i)\b(?:crear\s+un\s+virus|script\s+para\s+hackear|c[oó]mo\s+robar\s+contrase[ñn]as|generar\s+malware|troyano|keylogger|inyecci[oó]n\s+sql\s+para\s+vulnerar|hackear\s+wifi)\b",
     "Petición de generación de código malicioso o ciberataques"),

    # Criptomonedas, minería y esquemas financieros no académicos
    (r"(?i)\b(?:minar\s+(?:cripto|bitcoin|eth|moneda)|criptomonedas?|bitcoin|ethereum|forex|trading\s+binario)\b",
     "Consultas sobre criptomonedas o actividades financieras ajenas a la universidad"),

    # Groserías graves, acoso y contenido tóxico explícito
    (r"(?i)\b(?:malparid[ao]|hijo\s+de\s+puta|gonorrea|pirobo|carechimba|est[uú]pido\s+bot|mierda\s+de\s+sistema|imb[eé]cil|careverga)\b",
     "Uso de lenguaje soez, insultos o acoso contra la plataforma"),
]

# Benign greetings and capability inquiries (Allowed without strike, guided politely)
BENIGN_GREETING_PATTERNS = [
    r"(?i)^[¿¡\s]*(?:hola|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|buenas|hey|saludos)[.!?:;\s]*$",
    r"(?i)^[¿¡\s]*(?:(?:hola\s*)?(?:qui[eé]n\s+eres|qu[eé]\s+haces|qu[eé]\s+puedes\s+hacer|c[oó]mo\s+me\s+puedes\s+ayudar|c[oó]mo\s+funciona|para\s+qu[eé]\s+sirves|qu[eé]\s+es\s+este\s+sistema|qu[eé]\s+preguntas\s+puedo\s+hacer|ayuda))[.!?:;\s]*$",
]

# Broad Academic / University / Graduation Lexicon (Normalized for fast 0-token matching)
ACADEMIC_KEYWORDS = [
    # Grados y titulación
    "grado", "grados", "graduacion", "graduar", "graduando", "graduarme", "egresado", "titulacion",
    "diploma", "ceremonia", "acta de grado", "derechos de grado", "carpeta de grado",
    # Modalidades de trabajo de grado
    "modalidad", "modalidades", "pasantia", "pasantias", "monografia", "monografias", "tesis",
    "posgrado", "posgrados", "maestria", "especializacion", "semillero", "semilleros",
    "anteproyecto", "proyecto", "propuesta", "creacion de empresa", "produccion tecnica",
    "tecnologica", "articulo", "publicacion", "investigacion",
    # Roles y figuras académicas
    "asesor", "asesoria", "tutor", "tutoria", "director", "jurado", "jurados", "evaluador",
    "profesor", "profesores", "docente", "docentes", "decano", "decanatura", "coordinador",
    "coordinacion", "estudiante", "estudiantes", "consejero",
    # Requisitos, créditos, notas y cronograma
    "requisito", "requisitos", "credito", "creditos", "promedio", "ponderado", "nota", "notas",
    "calificacion", "calificaciones", "aprobacion", "reprobacion", "sustentacion", "sustentar",
    "informe", "prorroga", "plazo", "plazos", "fecha", "fechas", "calendario", "cronograma",
    "vencer", "vencimiento", "perder calidad", "sancion", "reclamo", "reclamacion", "saber pro",
    "icfes", "prerrequisito", "correquisito",
    # Trámites y dependencias administrativas
    "paz y salvo", "paz y salvos", "biblioteca", "bienestar", "laboratorio", "laboratorios",
    "carnet", "pecuniario", "recibo", "derechos pecuniarios", "arancel", "estampilla", "ventanilla",
    "secretaria", "secretaria academica", "proyecto curricular", "consejo academico",
    "consejo de facultad", "consejo superior", "comite", "tramite", "tramites", "solicitud",
    "solicitar", "radicar", "radicacion", "entrega", "entregar", "certificado", "constancia",
    "homologacion", "homologar", "transferencia", "reingreso", "matricula", "matricular",
    "cancelacion", "cancelar", "adicion", "adicionar", "cupo", "pensum", "malla", "plan de estudio",
    "plan de estudios", "asignatura", "asignaturas", "materia", "materias", "semestre", "periodo",
    "cohorte", "academico", "academica", "academia",
    # Lenguas y acreditación
    "ingles", "b2", "ilud", "idioma", "idiomas", "acreditacion", "acreditar", "suficiencia",
    "toefl", "ielts", "cambridge", "met",
    # Universidad Distrital e institucional
    "universidad", "distrital", "udistrital", "ud", "francisco jose de caldas", "facultad",
    "ingenieria", "sistemas", "sabio caldas", "macarena", "paiba", "bosa", "asab", "tecnologia",
    "acuerdo", "resolucion", "circular", "estatuto", "reglamento", "acuerdo 038", "acuerdo 027",
    "resolucion 004", "estatuto estudiantil", "norma", "normativa", "vigencia", "derog"
]


# ==============================================================================
# 2. CLIENT IDENTIFICATION & SUBNET EXTRACTION (IP, MAC, SUBNET, DEVICE ID)
# ==============================================================================

def extract_client_ip(request: Request) -> str:
    """
    Extracts the genuine client IP address taking into account Cloudflare,
    reverse proxies, and headers.
    """
    # 1. Cloudflare header
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    # 2. X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # 3. X-Forwarded-For (take the first public or left-most client IP)
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ips = [ip.strip() for ip in xff.split(",") if ip.strip()]
        if ips:
            return ips[0]

    # 4. Fallback to direct client host
    if request.client and request.client.host:
        return request.client.host.strip()

    return "127.0.0.1"


def calculate_subnet(ip_str: str) -> str:
    """
    Calculates the subnet /24 for IPv4 or /64 for IPv6 to prevent
    trivial network hop evasions.
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.version == 4:
            network = ipaddress.IPv4Network(f"{ip_str}/24", strict=False)
            return str(network)
        elif ip_obj.version == 6:
            network = ipaddress.IPv6Network(f"{ip_str}/64", strict=False)
            return str(network)
    except Exception:
        pass
    return ip_str


def extract_client_info(request: Request) -> Dict[str, str]:
    """
    Extracts comprehensive multi-factor client identifiers:
    - IP: Public/client IP address
    - Subnet: /24 or /64 network segment
    - MAC: Client hardware MAC / pseudo-MAC fingerprint passed in headers
    - Device ID: Persistent client UUID in localStorage / cookie
    - User-Agent: Browser & OS signature
    """
    ip = extract_client_ip(request)
    subnet = calculate_subnet(ip)
    
    device_id_query = ""
    mac_query = ""
    try:
        scope = getattr(request, "scope", {})
        if isinstance(scope, dict) and "query_string" in scope:
            device_id_query = request.query_params.get("device_id") or ""
            mac_query = request.query_params.get("mac") or ""
    except Exception:
        pass

    # Frontend provides persistent device UUID via header or query
    device_id = (
        request.headers.get("x-device-id") or
        request.headers.get("x-client-fingerprint") or
        device_id_query or
        ""
    ).strip()

    # Hardware MAC / pseudo-MAC identifier
    mac = (
        request.headers.get("x-mac-address") or
        request.headers.get("x-client-mac") or
        request.headers.get("x-device-mac") or
        mac_query or
        ""
    ).strip()

    user_agent = request.headers.get("user-agent", "unknown")[:300]

    return {
        "ip": ip,
        "subnet": subnet,
        "device_id": device_id,
        "mac": mac,
        "user_agent": user_agent,
    }


# ==============================================================================
# 3. SECURITY GUARDRAIL CHECK RESULT
# ==============================================================================

class GuardrailCheckResult:
    def __init__(
        self,
        is_safe: bool,
        is_greeting: bool = False,
        violation_type: Optional[str] = None,
        violation_reason: Optional[str] = None,
        direct_response: Optional[str] = None,
    ):
        self.is_safe = is_safe
        self.is_greeting = is_greeting
        self.violation_type = violation_type
        self.violation_reason = violation_reason
        self.direct_response = direct_response


def has_academic_context(text: str) -> bool:
    """
    Checks whether the text contains academic or university keywords.
    Uses strict word boundaries for short acronyms (e.g. 'ud', 'b2') to prevent
    false substring matches in non-academic words (e.g. 'feudal', 'ciudad', 'salud').
    """
    norm = normalize_text(text)
    for term in ACADEMIC_KEYWORDS:
        if len(term) <= 3:
            if re.search(r"\b" + re.escape(term) + r"\b", norm):
                return True
        else:
            if re.search(r"\b" + re.escape(term), norm):
                return True
    return False


def inspect_query_safety(
    query: str,
    history: Optional[List[Dict[str, str]]] = None
) -> GuardrailCheckResult:
    """
    Performs fast, 0-token security screening of student query:
    1. Empty and length check (Anti-DoS)
    2. Benign greeting check (orientation without strikes)
    3. Anti-prompt injection & jailbreak detection
    4. Explicit non-university abuse detection
    5. University domain relevance & conversational follow-up check
    """
    if not query or not query.strip():
        return GuardrailCheckResult(
            is_safe=False,
            violation_type="EMPTY_QUERY",
            violation_reason="La consulta no puede estar vacía."
        )

    q = query.strip()

    # 1. Length check
    if len(q) > MAX_QUERY_LENGTH:
        return GuardrailCheckResult(
            is_safe=False,
            violation_type="LENGTH_EXCEEDED",
            violation_reason=f"La consulta excede la longitud máxima permitida ({len(q)}/{MAX_QUERY_LENGTH} caracteres)."
        )

    # 2. Benign greeting check (Give direct orientation without penalty)
    for pattern in BENIGN_GREETING_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return GuardrailCheckResult(
                is_safe=True,
                is_greeting=True,
                direct_response=(
                    "¡Hola! 👋 Soy el Asistente Oficial de Grados de Ingeniería de Sistemas de la Universidad Distrital "
                    "Francisco José de Caldas. Estoy aquí para resolver tus dudas sobre modalidades de grado (pasantía, "
                    "monografía, posgrados, semilleros), requisitos de créditos, paz y salvos, acreditación de inglés B2 "
                    "y normatividad académica oficial. ¿En qué trámite de tu proceso de grado te puedo colaborar hoy?"
                )
            )

    # Normalized text for pattern & keyword matching
    q_norm = normalize_text(q)

    # 3. Anti-Prompting Attack & Jailbreak Detection (checked on raw and normalized)
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE) or re.search(pattern, q_norm, re.IGNORECASE):
            return GuardrailCheckResult(
                is_safe=False,
                violation_type="PROMPT_INJECTION",
                violation_reason="Intento de manipulación de directrices internas (Anti-Prompt Injection Gate activado)"
            )

    # 4. Off-Topic & Abuse Regexes (checked on raw and normalized)
    for pattern, reason in ABUSE_AND_OFFTOPIC_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE) or re.search(pattern, q_norm, re.IGNORECASE):
            return GuardrailCheckResult(
                is_safe=False,
                violation_type="OFF_TOPIC_ABUSE",
                violation_reason=reason
            )

    # 5. University Domain Relevance Gate
    has_academic_term = has_academic_context(q)

    if not has_academic_term:
        # Check if this is a natural conversational follow-up in an ongoing academic chat
        is_contextual_followup = False
        if history and len(history) > 0:
            # Check if previous context was academic
            recent_turns = history[-2:]
            history_text = " ".join(h.get("content", "") for h in recent_turns)
            history_has_academic = has_academic_context(history_text)

            if history_has_academic:
                # Check for common conversational follow-up inquiry patterns
                followup_patterns = [
                    r"\b(?:cuanto|cuanta|cuantos|cuantas)\b",
                    r"\b(?:donde|dond)\b",
                    r"\b(?:quien|quienes)\b",
                    r"\b(?:como|que|cual|cuales)\b",
                    r"\b(?:tiempo|duracion|plazo|demora|tarda)\b",
                    r"\b(?:costo|vale|precio|cobro|pagar)\b",
                    r"\b(?:entrega|entregar|radicar|enviar|firmar)\b",
                    r"\b(?:paso|pasos|requisito|opcion|primera|segunda)\b",
                    r"\b(?:si|no|pero|entonces|ademas)\b",
                ]
                if any(re.search(p, q_norm) for p in followup_patterns):
                    is_contextual_followup = True

        if not is_contextual_followup:
            return GuardrailCheckResult(
                is_safe=False,
                violation_type="OFF_TOPIC_ABUSE",
                violation_reason="Consulta sin temática académica ni universitaria detectada"
            )

    return GuardrailCheckResult(is_safe=True)


# ==============================================================================
# 4. STRIKE & 24-HOUR PENALTY MANAGER (IP, MAC, DEVICE, NETWORK)
# ==============================================================================

class SecurityStrikeRecord:
    def __init__(self, key: str):
        self.key = key
        self.strikes: int = 0
        self.banned_until: Optional[float] = None  # Unix timestamp
        self.violation_history: List[Dict[str, Any]] = []
        self.last_strike_time: float = 0.0
        self.linked_keys: set = set()


class SecurityStrikeManager:
    """
    Manages strikes and 24-hour bans across IP, MAC, Subnet, and Device ID.
    Enforces the 3-strike rule strictly with 0-token fast rejection.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._records: Dict[str, SecurityStrikeRecord] = {}

    def _get_record(self, key: str) -> SecurityStrikeRecord:
        if key not in self._records:
            self._records[key] = SecurityStrikeRecord(key)
        return self._records[key]

    def init_from_db(self, db: Session):
        """Restores active bans from DB on application startup."""
        try:
            from app.db.models import SecurityPenaltyLog
            now_dt = datetime.utcnow()
            now = time.time()
            active_bans = db.query(SecurityPenaltyLog).filter(
                SecurityPenaltyLog.is_banned == True,
                SecurityPenaltyLog.banned_until > now_dt
            ).all()

            with self._lock:
                for b in active_bans:
                    ban_remaining = (b.banned_until - now_dt).total_seconds()
                    ban_ts = now + ban_remaining
                    keys = [f"ip:{b.ip_address}"]
                    if b.device_id:
                        keys.append(f"dev:{b.device_id}")
                    if b.mac_address:
                        keys.append(f"mac:{b.mac_address}")
                    if b.subnet:
                        keys.append(f"subnet:{b.subnet}")

                    for k in keys:
                        rec = self._get_record(k)
                        rec.strikes = b.strike_count
                        rec.banned_until = ban_ts
                        rec.linked_keys.update(keys)
        except Exception as e:
            logger.error(f"[SecurityStrikeManager] Error loading bans from DB: {e}")

    def check_penalty(
        self,
        ip: str,
        subnet: str,
        device_id: Optional[str] = None,
        mac: Optional[str] = None
    ) -> Tuple[bool, int, Optional[str]]:
        """
        Checks if any client identifier (IP, MAC, Device ID, or Network Subnet)
        is currently under a 24-hour ban.
        Returns: (is_banned, remaining_seconds, ban_reason)
        """
        now = time.time()
        keys_to_check = [f"ip:{ip}", f"subnet:{subnet}"]
        if device_id:
            keys_to_check.append(f"dev:{device_id}")
        if mac:
            keys_to_check.append(f"mac:{mac}")

        with self._lock:
            for k in keys_to_check:
                if k in self._records:
                    rec = self._records[k]
                    if rec.banned_until and rec.banned_until > now:
                        remaining = int(rec.banned_until - now)
                        last_reason = (
                            rec.violation_history[-1].get("reason", "Infracción reiterada")
                            if rec.violation_history
                            else "Uso indebido reiterado"
                        )
                        return True, remaining, last_reason

        return False, 0, None

    def record_strike(
        self,
        ip: str,
        subnet: str,
        device_id: Optional[str],
        user_agent: str,
        query: str,
        violation_type: str,
        reason: str,
        mac: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Registers a strike against the client entity (IP, Device ID, MAC).
        When the client entity reaches 3 strikes, activates a 24-hour ban
        penalizing IP, MAC, Device ID, and the entire Network Subnet.
        """
        now = time.time()
        # Primary keys tracking the specific client actor:
        primary_keys = [f"ip:{ip}"]
        if device_id:
            primary_keys.append(f"dev:{device_id}")
        if mac:
            primary_keys.append(f"mac:{mac}")

        all_linked_keys = list(primary_keys)
        all_linked_keys.append(f"subnet:{subnet}")

        max_strike_count = 0
        is_now_banned = False
        remaining_seconds = 0

        with self._lock:
            for k in primary_keys:
                rec = self._get_record(k)
                rec.linked_keys.update(all_linked_keys)
                # If existing ban had expired, reset strikes
                if rec.banned_until and rec.banned_until <= now:
                    rec.strikes = 0
                    rec.banned_until = None

                rec.strikes += 1
                rec.last_strike_time = now
                rec.violation_history.append({
                    "time": datetime.utcnow().isoformat(),
                    "type": violation_type,
                    "reason": reason,
                    "query": query[:120],
                })

                if rec.strikes > max_strike_count:
                    max_strike_count = rec.strikes

            # If 3 strikes reached: activate 24h ban across IP, MAC, Device, and Subnet!
            if max_strike_count >= MAX_STRIKES:
                is_now_banned = True
                remaining_seconds = PENALTY_DURATION_SECONDS
                ban_timestamp = now + PENALTY_DURATION_SECONDS
                for k in all_linked_keys:
                    rec = self._get_record(k)
                    rec.linked_keys.update(all_linked_keys)
                    rec.banned_until = ban_timestamp
                    rec.strikes = max_strike_count
                    rec.violation_history.append({
                        "time": datetime.utcnow().isoformat(),
                        "type": violation_type,
                        "reason": reason,
                        "query": query[:120],
                    })

        # Persist penalty log into DB if session is provided
        if db:
            try:
                from app.db.models import SecurityPenaltyLog
                import json
                banned_dt = datetime.utcnow() + timedelta(seconds=PENALTY_DURATION_SECONDS) if is_now_banned else None
                log = SecurityPenaltyLog(
                    ip_address=ip,
                    mac_address=mac or None,
                    device_id=device_id or None,
                    subnet=subnet,
                    user_agent=user_agent,
                    strike_count=max_strike_count,
                    is_banned=is_now_banned,
                    banned_until=banned_dt,
                    last_reason=reason,
                    last_query=query[:300],
                    violation_history=json.dumps([
                        {"type": violation_type, "reason": reason, "query": query[:100]}
                    ])
                )
                db.add(log)
                db.commit()
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.error(f"[SecurityStrikeManager] Error saving to DB: {e}")

        # Formulate user warning or ban message
        if is_now_banned:
            hours = remaining_seconds // 3600
            mins = (remaining_seconds % 3600) // 60
            user_msg = (
                f"🚫 **Acceso Suspendido por 24 Horas (3/3 Strikes de Abuso):**\n\n"
                f"Tu dispositivo, dirección MAC y red IP (`{ip}`) han sido suspendidos temporalmente durante 24 horas "
                f"por acumular 3 envíos que no corresponden al ámbito académico de la Universidad Distrital o "
                f"que infringen las políticas de seguridad (Motivo: *{reason}*).\n\n"
                f"⏳ **Tiempo restante de penalización:** {hours} horas y {mins} minutos.\n\n"
                f"🔒 *Esta medida previene el consumo desmedido de tokens y protege la disponibilidad de la plataforma para la comunidad universitaria.*"
            )
        elif max_strike_count == 2:
            user_msg = (
                f"⚠️ **Advertencia Crítica de Seguridad (Strike 2 de 3):**\n\n"
                f"Segundo envío no permitido detectado (Motivo: *{reason}*).\n\n"
                f"🚨 **ÚLTIMO AVISO:** Si realizas 1 envío adicional fuera de la temática de grado o con intenciones "
                f"de abuso, tu dispositivo, dirección IP, MAC y red serán **bloqueados automáticamente durante 24 horas**."
            )
        else:
            user_msg = (
                f"⚠️ **Advertencia de Seguridad (Strike 1 de 3):**\n\n"
                f"Tu consulta ha sido detectada fuera del alcance académico de la Universidad Distrital "
                f"(Motivo: *{reason}*).\n\n"
                f"ℹ️ Este sistema está exclusivamente diseñado para responder dudas sobre grados, modalidades, pasantías, "
                f"inglés B2 y normatividad de Ingeniería de Sistemas. Al acumular **3 strikes**, se aplicará una "
                f"**penalización de 24 horas** sobre tu IP, MAC y dispositivo para evitar el agotamiento de recursos."
            )

        return {
            "strike_count": max_strike_count,
            "is_banned": is_now_banned,
            "remaining_seconds": remaining_seconds,
            "reason": reason,
            "message": user_msg
        }

    def list_penalties(self) -> List[Dict[str, Any]]:
        """Returns all current active strikes and bans for admin review."""
        now = time.time()
        results = []
        with self._lock:
            for key, rec in self._records.items():
                if rec.strikes > 0 or (rec.banned_until and rec.banned_until > now):
                    remaining = int(rec.banned_until - now) if rec.banned_until and rec.banned_until > now else 0
                    results.append({
                        "identifier": key,
                        "strikes": rec.strikes,
                        "is_banned": remaining > 0,
                        "remaining_seconds": remaining,
                        "remaining_hours": round(remaining / 3600, 1),
                        "violations": rec.violation_history[-5:],
                    })
        return results

    def revoke_penalty(self, identifier: str, db: Optional[Session] = None) -> bool:
        """Admins can unban an IP, MAC, Subnet, or Device ID manually, clearing in-memory and DB records."""
        with self._lock:
            clean_id = identifier.strip()
            sub = calculate_subnet(clean_id)
            keys_to_clear = {
                clean_id,
                f"ip:{clean_id}",
                f"dev:{clean_id}",
                f"mac:{clean_id}",
                f"subnet:{clean_id}",
                f"subnet:{sub}",
            }
            collected = set(keys_to_clear)
            for k, rec in self._records.items():
                if k in keys_to_clear or clean_id in k or sub in k:
                    collected.update(rec.linked_keys)

            found = False
            for k in list(self._records.keys()):
                if k in collected or any(c in k for c in keys_to_clear):
                    del self._records[k]
                    found = True

        if db:
            try:
                from app.db.models import SecurityPenaltyLog
                logs_to_update = db.query(SecurityPenaltyLog).filter(
                    (SecurityPenaltyLog.ip_address == clean_id) |
                    (SecurityPenaltyLog.device_id == clean_id) |
                    (SecurityPenaltyLog.mac_address == clean_id) |
                    (SecurityPenaltyLog.subnet == clean_id) |
                    (SecurityPenaltyLog.subnet == sub)
                ).all()
                for l in logs_to_update:
                    l.is_banned = False
                    l.banned_until = None
                    l.strike_count = 0
                db.commit()
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.error(f"[SecurityStrikeManager] Error revoking in DB: {e}")

        return found


# ==============================================================================
# 5. SLIDING-WINDOW VOLUMETRIC RATE LIMITER
# ==============================================================================

class SlidingWindowRateLimiter:
    """
    Thread-safe sliding-window rate limiter to protect API endpoints
    against volumetric DDoS, brute force, and token burning.
    Includes automatic memory cleanup of expired client records.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # map: route_category -> client_key -> list of timestamps
        self._buckets: Dict[str, Dict[str, List[float]]] = {}

    def is_rate_limited(
        self,
        endpoint_key: str,
        client_key: str,
        max_requests: int,
        window_seconds: int
    ) -> Tuple[bool, int]:
        """
        Evaluates whether a client has exceeded max_requests in window_seconds.
        Returns: (is_limited, retry_after_seconds)
        """
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            if endpoint_key not in self._buckets:
                self._buckets[endpoint_key] = {}

            endpoint_bucket = self._buckets[endpoint_key]
            if client_key not in endpoint_bucket:
                endpoint_bucket[client_key] = []

            timestamps = endpoint_bucket[client_key]
            # Prune expired timestamps
            valid_timestamps = [t for t in timestamps if t > cutoff]

            if len(valid_timestamps) >= max_requests:
                earliest = valid_timestamps[0]
                retry_after = max(1, int(earliest + window_seconds - now))
                endpoint_bucket[client_key] = valid_timestamps
                return True, retry_after

            valid_timestamps.append(now)
            endpoint_bucket[client_key] = valid_timestamps

            # Inline pruning to prevent memory leaks from inactive clients
            if len(endpoint_bucket) > 500:
                self._prune_bucket_unlocked(endpoint_bucket, cutoff)

            return False, 0

    def _prune_bucket_unlocked(self, bucket: Dict[str, List[float]], cutoff: float):
        for k in list(bucket.keys()):
            recent = [t for t in bucket[k] if t > cutoff]
            if not recent:
                del bucket[k]
            else:
                bucket[k] = recent

    def cleanup_old_records(self):
        """Periodic cleanup to avoid memory leak."""
        now = time.time()
        with self._lock:
            for endpoint, clients in list(self._buckets.items()):
                for client, timestamps in list(clients.items()):
                    recent = [t for t in timestamps if t > now - 3600]
                    if not recent:
                        del clients[client]
                    else:
                        clients[client] = recent


# Singletons
strike_manager = SecurityStrikeManager()
rate_limiter = SlidingWindowRateLimiter()
# Global concurrency semaphore for LLM stream calls (max 25 simultaneous streams)
STREAM_CONCURRENCY_SEMAPHORE = threading.Semaphore(25)
