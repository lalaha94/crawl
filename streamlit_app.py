import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from io import BytesIO

# Forsøk å importere pyrebase med Google Cloud Storage-støtte
try:
    import pyrebase
    from google.cloud import storage
except ModuleNotFoundError as e:
    st.error(f"Mangler nødvendig avhengighet: {e}. Prøv å oppdatere requirements.txt.")
    raise e

# Firebase-konfigurasjon hentet fra Streamlit Secrets
firebase_api_key = st.secrets.get("FIREBASE_API_KEY")

firebaseConfig = {
    "apiKey": firebase_api_key,
    "authDomain": st.secrets.get("FIREBASE_AUTH_DOMAIN"),
    "databaseURL": st.secrets.get("FIREBASE_DATABASE_URL"),
    "projectId": st.secrets.get("FIREBASE_PROJECT_ID"),
    "storageBucket": st.secrets.get("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": st.secrets.get("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": st.secrets.get("FIREBASE_APP_ID"),
    "measurementId": st.secrets.get("FIREBASE_MEASUREMENT_ID")
}

# Initialiser Firebase
firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()

# Funksjon for Google-innlogging
def google_login():
    st.title("Logg inn for å bruke tjenesten")
    email = st.text_input("E-post:")
    password = st.text_input("Passord:", type="password")
    if st.button("Logg inn"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.session_state["logged_in"] = True
            st.success(f"Velkommen, {email}!")
            st.rerun()
        except Exception as e:
            st.error(f"Innlogging mislyktes. Feil: {e}")

# Funksjon for å lage søketekst
def query(person):
    return '+'.join(person).replace(' ', '+').lower()

# Søk på Gule Sider
def gulesider(person):
    url = f'https://www.gulesider.no/{person}/personer'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, features="html.parser")
    tag = soup.find(attrs={
        'data-gmp-click': 'ps_hl_hit_phone_number_show_click'
    })
    if tag is None:
        return None
    return tag.text.strip()

# Søk på 1881
def _1881(person):
    url = f'https://www.1881.no/?query={person}'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, features="html.parser")
    tag = soup.find(attrs={
        'class': 'button-call__number'
    })
    if tag is None:
        return None
    return tag.text.strip()

# Finn telefonnummer fra Gule Sider eller 1881
def find_phone_number(person):
    phone_number = gulesider(person)
    if phone_number is None:
        return _1881(person)
    return phone_number

# Funksjon for å korrigere telefonnumre
def korriger_telefonnummer(telefon):
    if isinstance(telefon, str):
        telefon = telefon.replace(" ", "")
        if telefon.isdigit() and len(telefon) == 9:
            return telefon[1:]
    return telefon

# Sjekk om brukeren er logget inn
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    google_login()
else:
    # Streamlit App
    st.title("Telefonnummer-søker")
    st.write("Last opp en Excel-fil for å hente telefonnummer automatisk fra Gule Sider og 1881, må inneholde Eier Fornavn, Eier Etternavn, Eier Postnummer.")

    uploaded_file = st.file_uploader("Last opp Excel-fil", type=["xlsx"])

    if uploaded_file:
        df = pd.read_excel(uploaded_file, sheet_name=0)
        st.write("## Data forhåndsvisning:")
        st.dataframe(df.head())

        # Filtrere ut selskaper
        df = df[df['Eier Fornavn'].notna()]

        # Rens postnummer
        df['Eier Postnummer'] = df['Eier Postnummer'].apply(lambda x: str(int(float(x))) if '.' in str(x) else str(x))

        # Lag søketekst
        df['søk'] = df[['Eier Fornavn', 'Eier Etternavn', 'Eier Postnummer']].apply(query, axis=1)

        # Hent telefonnummer med statusindikator
        with st.spinner('Søker etter telefonnumre, vennligst vent...'):
            status = st.empty()
            phone_numbers = []
            for index, row in df.iterrows():
                status_text = f"Behandler {index + 1} av {len(df)}: {row['Eier Fornavn']} {row['Eier Etternavn']}"
                status.text(status_text)
                phone_number = find_phone_number(row['søk'])
                phone_numbers.append(phone_number)
            df['Telefon'] = phone_numbers

        # Korriger telefonnumrene
        df['Telefon'] = df['Telefon'].apply(korriger_telefonnummer)

        st.success('Søket og korrigeringen er ferdig!')
        st.write("## Oppdatert data:")
        st.dataframe(df)

        # Gjør klar for nedlasting
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        st.download_button(
            label="Last ned oppdatert Excel-fil",
            data=output,
            file_name="leads_med_korrigerte_telefonnumre.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Vennligst last opp en Excel-fil for å starte søket.")
