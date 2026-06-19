import pyotp
import qrcode
import io
import base64


def generate_totp_secret() -> str:
    """
    Generates a secure, random 32-character Base32 secret.
    This secret is what the user stores in their Google Authenticator app.
    """
    return pyotp.random_base32()


def get_totp_uri(username: str, secret: str) -> str:
    """
    Creates the 'otpauth://' URI.
    When scanned, this URI tells the app the issuer name and the secret key.
    """
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="Xgrid-MFA-Gate"
    )


def generate_qr_code_base64(uri: str) -> str:
    """
    Converts the URI into a PNG image and encodes it as a base64 string.
    This allows your frontend (or Swagger) to render the image directly.
    """
    # 1. Generate the image
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # 2. Save image to a memory buffer (so we don't need to save files to disk)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    # 3. Convert bytes to base64 string
    encoded_img = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded_img}"


def verify_totp_code(secret: str, input_code: str) -> bool:
    """
    Validates the 6-digit code provided by the user.
    The 'valid_window=1' allows for a slight time drift between phones and servers.
    """
    if not secret:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(input_code, valid_window=1)