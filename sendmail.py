import os
import re
from dotenv import load_dotenv
from imap_tools import MailBox, AND
from pypdf import PdfReader, PdfWriter

# Importamos las funciones desarrolladas en extract.py
from extract import extraer_movimientos_sabadell, guardar_en_postgresql

# Cargar variables del entorno (.env)
load_dotenv()

REMITENTE_BUSCADO = "mail@bancsabadell.com"
MI_CORREO = "oriolbrotons@gmail.com"
PASSWORD = os.getenv("EMAIL_PASSWORD")
PDF_PASS = os.getenv("PDF_PASS")

CARPETA_ADJUNTOS = "adjuntos"

if not PASSWORD:
    raise ValueError("❌ No se encontró EMAIL_PASSWORD en el archivo .env")

if not PDF_PASS:
    print("⚠️ ADVERTENCIA: No se encontró la variable PDF_PASS en el archivo .env")

os.makedirs(CARPETA_ADJUNTOS, exist_ok=True)


def sanitizar_nombre(filename: str) -> str:
    filename = os.path.basename(filename)
    return re.sub(r'[^\w\.-]', '_', filename)


def extraer_cuenta_desde_nombre(nombre_archivo: str) -> str:
    match = re.search(r'(\d{4}_\d{4}_\d{3}_\d{6})', nombre_archivo)
    if match:
        partes = match.group(1).split('_')
        return f"{partes[0]}-{partes[1]}-{partes[2]}{partes[3]}"
    return "SABADEL_GENERAL"


def desbloquear_pdf(ruta_pdf: str, password: str) -> str:
    if not password:
        print("⚠️ Imposible desencriptar: Contraseña no configurada en .env.")
        return ruta_pdf

    try:
        reader = PdfReader(ruta_pdf)
        if reader.is_encrypted:
            print("🔒 PDF encriptado detectado. Desbloqueando...")
            if reader.decrypt(password):
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)

                ruta_desbloqueado = ruta_pdf.replace(".pdf", "_unlocked.pdf")
                with open(ruta_desbloqueado, "wb") as f:
                    writer.write(f)
                return ruta_desbloqueado
            else:
                print("❌ La contraseña PDF_PASS no es correcta.")
                return None
        else:
            return ruta_pdf
    except Exception as e:
        print(f"⚠️ Error procesando el PDF: {e}")
        return None


def eliminar_archivo_local(ruta: str):
    """Elimina de forma segura un archivo local si existe."""
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
            print(f"🗑️ Archivo borrado del disco: {ruta}")
    except Exception as e:
        print(f"⚠️ No se pudo eliminar el archivo {ruta}: {e}")


def mover_a_papelera(mailbox, msg_uid):
    """Mueve un mensaje a la papelera de Gmail."""
    try:
        mailbox.move(msg_uid, '[Gmail]/Papelera')
        print("🗑️ Correo movido a la Papelera en Gmail.")
    except Exception:
        try:
            mailbox.move(msg_uid, '[Gmail]/Trash')
            print("🗑️ Correo movido a Trash en Gmail.")
        except Exception as e:
            print(f"⚠️ Error al eliminar el correo de Gmail: {e}")


print(f"🔍 Buscando correos de {REMITENTE_BUSCADO}...")

with MailBox('imap.gmail.com').login(MI_CORREO, PASSWORD, initial_folder='INBOX') as mailbox:
    for msg in mailbox.fetch(AND(from_=REMITENTE_BUSCADO)):
        print("-" * 50)
        print(f"📅 Fecha:  {msg.date}")
        print(f"📧 Asunto: {msg.subject}")

        procesado_con_exito = False

        if msg.attachments:
            print("📎 Adjuntos encontrados:")
            for att in msg.attachments:
                if att.filename:
                    nombre_seguro = sanitizar_nombre(att.filename)
                    ruta_archivo = os.path.join(CARPETA_ADJUNTOS, nombre_seguro)

                    # 1. Descargar adjunto
                    with open(ruta_archivo, 'wb') as f:
                        f.write(att.payload)
                    print(f"   📥 Guardado temporalmente: {CARPETA_ADJUNTOS}/{nombre_seguro}")

                    # 2. Desbloquear e procesar PDF
                    if nombre_seguro.lower().endswith(".pdf"):
                        ruta_pdf_listo = desbloquear_pdf(ruta_archivo, PDF_PASS)

                        if ruta_pdf_listo and os.path.exists(ruta_pdf_listo):
                            cuenta = extraer_cuenta_desde_nombre(nombre_seguro)
                            print(f"⚙️ Procesando extracto para la cuenta: {cuenta}...")
                            df_movimientos = extraer_movimientos_sabadell(ruta_pdf_listo, cuenta)

                            if not df_movimientos.empty:
                                # Guardar en PostgreSQL
                                guardar_en_postgresql(df_movimientos)
                                procesado_con_exito = True

                        # 3. Eliminar archivos locales (original y desencriptado)
                        eliminar_archivo_local(ruta_archivo)
                        if ruta_pdf_listo != ruta_archivo:
                            eliminar_archivo_local(ruta_pdf_listo)
        
        # 4. Si se procesó con éxito o no tenía adjuntos, mover el mail a la papelera
        if procesado_con_exito or not msg.attachments:
            mover_a_papelera(mailbox, msg.uid)

print("-" * 50)
print("✅ Proceso completo: Correos procesados, datos en PostgreSQL, archivos y mails eliminados.")
