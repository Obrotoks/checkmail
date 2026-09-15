import os
import re
from datetime import datetime
import pdfplumber
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# 1. Cargar variables del archivo .env
load_dotenv()


def obtener_anio_desde_pdf(ruta_pdf):
    # Extrae el año (4 dígitos al inicio) del nombre del archivo, e.g., 20260831 -> 2026
    nombre_archivo = os.path.basename(ruta_pdf)
    match = re.match(r"^(\d{4})", nombre_archivo)
    return match.group(1) if match else str(datetime.now().year)


def parsear_fecha_ddmm(cadena_ddmm, anio):
    # Convierte '3108' en '2026-08-31'
    dia = cadena_ddmm[:2]
    mes = cadena_ddmm[2:]
    return f"{anio}-{mes}-{dia}"


def extraer_movimientos_sabadell(ruta_pdf, cuenta):
    movimientos = []
    anio_pdf = obtener_anio_desde_pdf(ruta_pdf)

    with pdfplumber.open(ruta_pdf) as pdf:
        for page in pdf.pages:
            texto = page.extract_text(layout=True)
            if not texto:
                continue

            lineas = texto.split("\n")

            for linea in lineas:
                # Regex adaptado para tolerar espacios u omisiones entre números y letras H/D
                patron = r"^(\d{4})\s+(.*?)\s+(\d{4})\s+([\d\.,]+\s*[DH])\s+([\d\.,]+\s*[HD])$"
                match = re.search(patron, linea.strip())

                if match:
                    (
                        fecha_raw,
                        concepto,
                        fecha_valor_raw,
                        importe_raw,
                        saldo_raw,
                    ) = match.groups()

                    # Convertir fechas a YYYY-MM-DD
                    fecha_iso = parsear_fecha_ddmm(fecha_raw, anio_pdf)
                    fecha_valor_iso = parsear_fecha_ddmm(
                        fecha_valor_raw, anio_pdf
                    )

                    # Importe a float (limpieza robusta con regex)
                    es_cargo = "D" in importe_raw
                    importe_clean = re.sub(
                        r"[^\d,-]", "", importe_raw
                    ).replace(".", "").replace(",", ".")
                    importe_num = float(importe_clean)
                    if es_cargo:
                        importe_num = -importe_num

                    # Saldo a float (limpieza robusta con regex)
                    es_saldo_deudor = "D" in saldo_raw
                    saldo_clean = re.sub(r"[^\d,-]", "", saldo_raw).replace(
                        ".", ""
                    ).replace(",", ".")
                    saldo_num = float(saldo_clean)
                    if es_saldo_deudor:
                        saldo_num = -saldo_num

                    movimientos.append(
                        {
                            "fecha": fecha_iso,
                            "concepto": concepto.strip(),
                            "fecha_valor": fecha_valor_iso,
                            "importe": importe_num,
                            "saldo": saldo_num,
                            "cuenta": cuenta,
                        }
                    )

    return pd.DataFrame(movimientos)


def guardar_en_postgresql(df):
    DB_USER = os.getenv("POSTGRES_USER") or "f00"
    DB_PASS = os.getenv("POSTGRES_PASSWORD")
    DB_HOST = os.getenv("POSTGRES_HOST", "192.168.68.100")
    DB_PORT = os.getenv("POSTGRES_PORT", "5432")
    DB_NAME = os.getenv("POSTGRES_DB", "finanzas")

    if not DB_PASS:
        raise ValueError(
            "❌ ERROR: La variable POSTGRES_PASSWORD no está definida en el archivo .env"
        )

    cadena_conexion = (
        f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    engine = create_engine(cadena_conexion)

    with engine.begin() as conn:
        # 1. Crear la tabla si no existe con Constraint UNIQUE y TIMESTAMP automático
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS movimientos_sabadell (
                id SERIAL PRIMARY KEY,
                fecha DATE NOT NULL,
                concepto TEXT NOT NULL,
                fecha_valor DATE,
                importe NUMERIC(12, 2) NOT NULL,
                saldo NUMERIC(12, 2) NOT NULL,
                cuenta VARCHAR(50) NOT NULL,
                fecha_insercion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT unique_movimiento UNIQUE (fecha, concepto, importe, saldo, cuenta)
            );
        """
            )
        )

        # 2. Inserción con ON CONFLICT DO NOTHING para evitar duplicados
        sql_insert = text(
            """
            INSERT INTO movimientos_sabadell (fecha, concepto, fecha_valor, importe, saldo, cuenta)
            VALUES (:fecha, :concepto, :fecha_valor, :importe, :saldo, :cuenta)
            ON CONFLICT ON CONSTRAINT unique_movimiento DO NOTHING;
        """
        )

        registros = df.to_dict(orient="records")
        conn.execute(sql_insert, registros)

    print(
        "\n🚀 Movimientos procesados e insertados con éxito en PostgreSQL (omitiendo duplicados)."
    )


# --- Bloque de Ejecución Principal ---
if __name__ == "__main__":
    ruta_pdf = "adjuntos/20260831_EXTRACTO_0081_5661_001_006667_unlocked.pdf"
    cuenta_nombre = "ES89-0081-5661-0016667"  # Puedes cambiar "test" por el alias o IBAN deseado

    if os.path.exists(ruta_pdf):
        df_resultado = extraer_movimientos_sabadell(ruta_pdf, cuenta_nombre)
        print("📊 Movimientos extraídos:")
        print(df_resultado.to_string())

        if not df_resultado.empty:
            guardar_en_postgresql(df_resultado)
    else:
        print(f"❌ No se encontró el archivo: {ruta_pdf}")
