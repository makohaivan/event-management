"""QR code images for tickets."""
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def qr_payload(registration):
    """
    The text stored inside the QR code: the registration's secret token.
    Attendance scanning (Phase 8) looks this token up to find the registration.
    """
    return str(registration.qr_token)


def make_qr_png(data, box_size=8, border=2):
    """Return a PNG image (as bytes) of a QR code holding `data`."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=box_size, border=border)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
