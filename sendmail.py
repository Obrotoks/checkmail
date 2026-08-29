import email.message
import os
import smtplib
from dotenv import load_dotenv

# Carga la variable EMAIL_PASSWORD desde el archivo .env
load_dotenv()

REMITENTE = "oriolbrotons@gmail.com"
PASSWORD = os.getenv("EMAIL_PASSWORD")

if not PASSWORD:
    raise ValueError(
        "❌ No se encontró EMAIL_PASSWORD en el archivo .env"
    )

# Resto del código de envío SMTP...


# --- ENVIAR CORREO ---
msg = email.message.EmailMessage()
msg["Subject"] = "Prueba con Keyring"
msg["From"] = REMITENTE
msg["To"] = "oriolbrotons@hotmail.com"
msg.set_content("Correo enviado recuperando clave con Keyring.")

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(REMITENTE, PASSWORD)
    server.send_message(msg)

print("✅ Correo enviado con éxito.")
