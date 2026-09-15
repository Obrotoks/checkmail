import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Finanzas Sabadell", layout="wide")
st.title("🏦 Dashboard de Movimientos Bancarios")

# Conexión a la base de datos
DB_USER = os.getenv("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "finanzas")

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Cargar datos
df = pd.read_sql("SELECT fecha, concepto, importe, saldo, cuenta, fecha_insercion FROM movimientos_sabadell ORDER BY fecha DESC, id DESC", engine)

# Métricas rápidas
col1, col2, col3 = st.columns(3)
col1.metric("Total Movimientos", len(df))
col2.metric("Último Saldo", f"{df['saldo'].iloc[0]:,.2f} €" if not df.empty else "0 €")

gastos = df[df['importe'] < 0]['importe'].sum()
col3.metric("Total Gastos", f"{gastos:,.2f} €")

# Gráfico de evolución del saldo
st.subheader("📈 Evolución del Saldo")
st.line_chart(df.set_index('fecha')['saldo'])

# Tabla interactiva con filtro
st.subheader("📋 Registro de Movimientos")
filtro = st.text_input("🔍 Buscar por concepto:")
if filtro:
    df = df[df['concepto'].str.contains(filtro, case=False)]

st.dataframe(df, use_container_width=True)
