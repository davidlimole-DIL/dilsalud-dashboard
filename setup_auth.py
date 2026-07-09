# ============================================================
# DIL-Salud — Script de autenticación (ejecutar UNA SOLA VEZ)
# ============================================================
# Este script abre el navegador para que autorices el acceso
# a Google Sheets con tu cuenta de Google.
# El token se guarda localmente y el Dashboard lo reutiliza.
# ============================================================

import gspread

print()
print("=" * 55)
print("  DIL-Salud — Autorización de Google Sheets")
print("=" * 55)
print()
print("  Se va a abrir tu navegador para que autorices")
print("  el acceso a Google Sheets con tu cuenta de Google.")
print()
print("  Si no se abre automáticamente, copiá la URL")
print("  que aparece en la terminal y pegala en el navegador.")
print()

gc = gspread.oauth(
    credentials_filename=".streamlit/client_secret.json",
    authorized_user_filename=".streamlit/authorized_user.json",
    scopes=[
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ],
)

print()
print("✅ ¡Autenticación exitosa!")
print()
print("   Token guardado en: .streamlit/authorized_user.json")
print("   Ya podés ejecutar:  streamlit run app.py")
print()
