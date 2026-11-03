"""Parser-free upload admission shared by UI, controller, executor and worker."""
import base64
import binascii
import json

PDF_BYTES = 25*1024*1024
IMAGE_BYTES = 5*1024*1024
TOTAL_BYTES = 60*1024*1024
FIELDS = {"pdf", "baseline", "signature_image", "reference_image"}


class InputRejected(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def validate_inputs(values):
    if not isinstance(values, dict) or "pdf" not in values or set(values)-FIELDS:
        raise InputRejected("invalid_request", "Unsupported analysis request fields.")
    if any(not isinstance(value, bytes) for value in values.values()):
        raise InputRejected("invalid_request", "Analysis inputs must be bytes.")
    if sum(map(len, values.values())) > TOTAL_BYTES:
        raise InputRejected("input_limit", "Combined input exceeds 60 MiB.")
    for name, value in values.items():
        pdf = name in {"pdf", "baseline"}
        if not value or len(value) > (PDF_BYTES if pdf else IMAGE_BYTES):
            raise InputRejected("input_limit", "PDFs must be 1 byte–25 MiB; images 1 byte–5 MiB.")
        if pdf and not value.startswith(b"%PDF-"):
            raise InputRejected("invalid_pdf", "Expected PDF bytes; filename and MIME type are insufficient.")
        if not pdf and not value.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")):
            raise InputRejected("invalid_image", "Optional signature images must contain PNG or JPEG bytes.")
    return values


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputRejected("invalid_request", "Duplicate request field.")
        result[key] = value
    return result


def decode_request(payload):
    try:
        values = json.loads(payload, object_pairs_hook=_unique)
        if not isinstance(values, dict) or "pdf" not in values or set(values)-FIELDS:
            raise InputRejected("invalid_request", "Unsupported analysis request fields.")
        decoded = {}
        for key, value in values.items():
            limit = PDF_BYTES if key in {"pdf", "baseline"} else IMAGE_BYTES
            if not isinstance(value, str) or len(value) > 4*((limit+2)//3):
                raise InputRejected("input_limit", "Encoded input exceeds field limit.")
            decoded[key] = base64.b64decode(value, validate=True)
        return validate_inputs(decoded)
    except InputRejected:
        raise
    except (ValueError, TypeError, binascii.Error, UnicodeError) as exc:
        raise InputRejected("invalid_request", "Invalid analysis request encoding.") from exc
