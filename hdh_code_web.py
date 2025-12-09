import streamlit as st
import pandas as pd
import re
import os
import sys
from io import BytesIO

import requests
from bs4 import BeautifulSoup
import time
# ==================== CONFIGURATION DE LA PAGE ====================
st.set_page_config(
    page_title="Moteur de recherche des projets",
    page_icon="🔍",
    layout="wide"
)
# ==================== CSS PERSONNALISÉ ====================
st.markdown("""
<style>
    /* Styles compatibles avec les thèmes clair et sombre */
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 3px solid #1f77b4;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.2rem;
        font-weight: bold;
        margin: 2rem 0 1rem 0;
    }
    .filter-title {
        font-weight: bold;
        color: #D32F2F;
        font-size: 0.9rem;
        margin-bottom: 0.3rem;
    }
    .article-field-label {
        font-weight: bold;
        color: #D32F2F;
        font-size: 1.1rem;
        margin-top: 1rem;
    }
    .article-field-value {
        font-size: 1rem;
        margin-bottom: 1rem;
        padding-left: 1rem;
        background-color: rgba(128, 128, 128, 0.1);
        padding: 0.5rem;
        border-radius: 5px;
    }
    .article-field-empty {
        color: #757575;
        font-style: italic;
        font-size: 1rem;
        margin-bottom: 1rem;
        padding-left: 1rem;
    }
    .stButton>button {
        width: 100%;
    }
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    
    /* Amélioration de la lisibilité pour les thèmes sombres */
    [data-testid="stMarkdownContainer"] p {
        color: inherit;
    }
</style>
""", unsafe_allow_html=True)



# ==================== TITRE DE L'APPLICATION ====================
st.markdown('<div class="main-header">Moteur de recherche des projets</div>', unsafe_allow_html=True)

# ==================== BOUTON DE RAFRAÎCHISSEMENT ====================
col_refresh1, col_refresh2, col_refresh3 = st.columns([1, 1, 1])
with col_refresh2:
    if st.button("🔄 Actualiser les données", use_container_width=True, help="Récupère les dernières données depuis le site HDH"):
        st.cache_data.clear()
        st.rerun()


# scrapping
@st.cache_data(ttl=3600)  # Cache pendant 1 heure
def load_data():
    """
    Charge les données depuis le site HDH en scrapant le lien de téléchargement
    """
    try:
        url = "https://www.health-data-hub.fr/projets"
        
        # Headers plus complets pour éviter les blocages
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        st.info("🔄 Récupération de la page HDH...")
        
        # Récupérer la page avec session pour maintenir les cookies
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parser le HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Stratégies multiples pour trouver le lien Excel
        download_link = None
        
        # Stratégie 1: Chercher les liens avec des mots-clés dans le texte
        st.info("🔍 Recherche du lien de téléchargement...")
        
        # Rechercher tous les liens
        all_links = soup.find_all('a', href=True)
        
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True).lower()
            
            # Vérifier si c'est un fichier Excel
            if any(ext in href.lower() for ext in ['.xlsx', '.xls']):
                download_link = href
                st.info(f"✅ Lien Excel trouvé par extension: {href}")
                break
            
            # Vérifier si le texte contient des mots-clés de téléchargement
            if any(keyword in text for keyword in ['télécharger', 'download', 'excel', 'xlsx']):
                # Vérifier si le lien pointe vers un fichier ou une page de téléchargement
                if href and not href.startswith('#'):
                    download_link = href
                    st.info(f"✅ Lien trouvé par mot-clé '{text}': {href}")
                    break
        
        # Stratégie 2: Chercher dans les attributs data-* ou onclick
        if not download_link:
            for element in soup.find_all(['a', 'button', 'div']):
                for attr_name, attr_value in element.attrs.items():
                    if isinstance(attr_value, str) and any(ext in attr_value.lower() for ext in ['.xlsx', '.xls']):
                        download_link = attr_value
                        st.info(f"✅ Lien trouvé dans l'attribut {attr_name}: {attr_value}")
                        break
                if download_link:
                    break
        
        # Stratégie 3: Chercher des patterns spécifiques au site HDH
        if not download_link:
            # Chercher des liens vers des fichiers ou APIs
            for link in all_links:
                href = link.get('href', '')
                if any(pattern in href.lower() for pattern in ['/api/', '/download/', '/file/', '/export/']):
                    # Vérifier si ça pourrait être notre fichier
                    if 'projet' in href.lower() or 'repertoire' in href.lower():
                        download_link = href
                        st.info(f"✅ Lien API/Download trouvé: {href}")
                        break
        
        if not download_link:
            st.error("❌ Impossible de trouver le lien de téléchargement Excel")
            st.info("🔍 Liens trouvés sur la page:")
            
            # Afficher quelques liens pour debug
            for i, link in enumerate(all_links[:10]):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                st.write(f"- {text[:50]}... → {href[:100]}...")
            
            return load_fallback_data()
        
        # Construire l'URL complète
        if download_link.startswith('/'):
            download_link = "https://www.health-data-hub.fr" + download_link
        elif not download_link.startswith('http'):
            download_link = "https://www.health-data-hub.fr/" + download_link.lstrip('/')
        
        st.info(f"📥 Téléchargement depuis: {download_link}")
        
        # Télécharger le fichier Excel
        excel_response = session.get(download_link, headers=headers, timeout=60)
        excel_response.raise_for_status()
        
        # Vérifier que c'est bien un fichier Excel
        content_type = excel_response.headers.get('content-type', '').lower()
        if 'excel' not in content_type and 'spreadsheet' not in content_type:
            st.warning(f"⚠️ Type de contenu inattendu: {content_type}")
        
        # Lire le fichier Excel depuis la mémoire
        df = pd.read_excel(BytesIO(excel_response.content), engine="openpyxl")
        
        st.success(f"✅ Données chargées avec succès ! ({len(df)} projets trouvés)")
        
        return df
        
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erreur de connexion au site HDH : {e}")
        return load_fallback_data()
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des données : {e}")
        return load_fallback_data()

def load_fallback_data():
    """
    Fonction de secours : charge le fichier local si le scraping échoue
    """
    try:
        base_path = os.path.dirname(__file__)
        file_path = os.path.join(base_path, "repertoire_projets.xlsx")
        
        if os.path.exists(file_path):
            st.warning("⚠️ Utilisation du fichier local de secours")
            df = pd.read_excel(file_path, engine="openpyxl")
            st.info(f"📁 Fichier local chargé ({len(df)} projets)")
            return df
        else:
            st.error("❌ Aucun fichier de secours trouvé")
            st.info("💡 Vous pouvez télécharger manuellement le fichier Excel depuis https://www.health-data-hub.fr/projets et le placer dans le dossier de l'application")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement du fichier de secours : {e}")
        return pd.DataFrame()
        
df = load_data()

if df.empty:
    st.warning("Aucune donnée n'a été chargée. L'application ne peut pas fonctionner correctement.")
    st.stop()

# Fonction pour normaliser et enrichir les sources de données
def normalize_and_enrich_sources(row):
    """
    Enrichit la colonne 'Source de données utilisées' avec :
    - Les composantes SNDS si SNDS est mentionné
    - Les bases HDH si HDH est mentionné
    - Les autres sources si 'autre' est mentionné
    - Force ESND et Causes médicales de décès dans SNDS
    """
    source_principale = str(row.get("Source de données utilisées", ""))

    if pd.isna(source_principale) or source_principale == "nan":
        return ""

    sources_enrichies = []
    sources_snds_trouvees = set()
    has_explicit_snds = False

    parts = re.split(r",", source_principale)

    for part in parts:
        part_clean = clean_value(part)

        if not part_clean:
            continue

        # Cas 1 : SNDS explicitement mentionné
        if re.search(r'\bSNDS\b', part_clean, re.IGNORECASE):
            has_explicit_snds = True

            # Ajouter les composantes du SNDS
            composantes_snds = clean_value(row.get("Composante(s) de la base principale du SNDS mobilisée(s)", ""))
            if composantes_snds:
                sous_composantes = re.split(r",", composantes_snds)
                for sc in sous_composantes:
                    sc_clean = clean_value(sc)
                    if sc_clean:
                        sources_snds_trouvees.add(sc_clean)

        # Cas 2 : HDH mentionné
        elif re.search(r'\bHDH\b', part_clean, re.IGNORECASE):
            sources_enrichies.append("HDH")

            # Ajouter les bases du HDH
            bases_hdh = clean_value(row.get("Base(s) du catalogue du HDH mobilisée(s)", ""))
            if bases_hdh:
                sous_bases = re.split(r",", bases_hdh)
                for sb in sous_bases:
                    sb_clean = clean_value(sb)
                    if sb_clean:
                        sources_enrichies.append(f"HDH - {sb_clean}")

        # Cas 3 : Autre/Autres mentionné
        elif re.search(r'\bAutre\(?\s*s\)?\b|\bautres?\b', part_clean, re.IGNORECASE):
            autres_sources = clean_value(row.get("Autre(s) source(s) de donnée(s) mobilisée(s)", ""))

            if autres_sources:
                sous_autres = re.split(r",", autres_sources)
                for sa in sous_autres:
                    sa_clean = clean_value(sa)
                    if sa_clean:
                        # Vérifier si cette "autre source" fait partie du SNDS
                        if is_snds_component(sa_clean):
                            sources_snds_trouvees.add(sa_clean)
                            has_explicit_snds = True
                        else:
                            sources_enrichies.append(sa_clean)
            else:
                sources_enrichies.append("Autres")

        # Cas 4 : Composante SNDS directe (ESND, Causes médicales de décès, etc.)
        elif is_snds_component(part_clean):
            sources_snds_trouvees.add(part_clean)
            has_explicit_snds = True

        # Cas 5 : Autre source non catégorisée
        else:
            if part_clean:
                sources_enrichies.append(part_clean)

    # Si on a trouvé des composantes SNDS ou SNDS explicite, ajouter SNDS + composantes
    if has_explicit_snds or sources_snds_trouvees:
        # Ajouter SNDS en premier
        final_sources = ["SNDS"]

        # Ajouter toutes les composantes trouvées
        for composante in sorted(sources_snds_trouvees):
            final_sources.append(f"SNDS - {composante}")

        # Ajouter les autres sources
        final_sources.extend(sources_enrichies)

        return ", ".join(final_sources)

    # Sinon, retourner les sources normales
    return ", ".join(sources_enrichies) if sources_enrichies else ""

# Fonction pour normaliser les termes "Autre/Autres" génériques
def normalize_autres(text):
    """Normalise 'Autre' et 'Autres' vers 'Autres' (pour les autres colonnes)"""
    if pd.isna(text):
        return text
    text_str = str(text)

    # Normaliser Autres) → Autres
    text_str = re.sub(r'\bAutres\)\b', 'Autres', text_str, flags=re.IGNORECASE)

    # Normaliser Autre(s) → Autres
    text_str = re.sub(r'\bAutre\(?\s*s\)?\b', 'Autres', text_str, flags=re.IGNORECASE)
    text_str = re.sub(r'\bautres?\b', 'Autres', text_str, flags=re.IGNORECASE)

    return text_str

# Fonction pour déterminer le statut basé sur la colonne "Etape : Complétude"
def determine_status(value):
    """
    Détermine le statut du projet :
    - "Terminé" si la cellule contient une date (non vide)
    - "En cours" si la cellule est vide
    """
    if pd.isna(value) or str(value).strip() == "" or str(value).lower() == "nan":
        return "En cours"
    else:
        return "Terminé"

# ==================== FONCTIONS DE NETTOYAGE DES DONNÉES ====================

def clean_value(text):
    """Nettoie les valeurs indésirables et applique les normalisations de base"""
    if pd.isna(text) or str(text).lower() == "nan":
        return ""

    text_str = str(text).strip()

    # Enlever les underscores seuls
    if text_str == "_" or text_str == "":
        return ""

    # Normaliser "Bases des causes médicales de décès (CépiDC)" → "Causes médicales de décès"
    text_str = re.sub(r'Bases?\s+des?\s+causes?\s+médicales?\s+de\s+décès\s*\(CépiDC\)', 
                      'Causes médicales de décès', text_str, flags=re.IGNORECASE)

    # Normaliser "Echantillon du ENSD" → "ESND"
    text_str = re.sub(r'Echantillon\s+du\s+ENSD', 'ESND', text_str, flags=re.IGNORECASE)

    #  Normaliser toutes les variantes de Enquête(s), enquêtes, etc. → Enquête
    text_str = re.sub(r'\benqu[êe]te(?:\s*\(?s\)?|\s*s)?\b', 'Enquêtes', text_str, flags=re.IGNORECASE)

    #  Normaliser toutes les variantes de Autre(s), autres, etc. → Autres
    text_str = re.sub(r'\bautre(?:\s*\(?s\)?|\s*s)?\b', 'Autres', text_str, flags=re.IGNORECASE)

    #  Supprimer parenthèses fermantes orphelines après Enquête ou Autres
    text_str = re.sub(r'\b(Enquête|Autres)\)', r'\1', text_str, flags=re.IGNORECASE)

    return text_str

def is_snds_component(source_name):
    """Vérifie si une source fait partie du SNDS"""
    snds_components = [
        'causes médicales de décès',
        'esnd',
        'dcir',
        'pmsi',
        'certificats de décès',
        'rniam'
    ]

    for component in snds_components:
        if component in source_name.lower():
            return True
    return False

# ==================== APPLICATION DES TRANSFORMATIONS ====================
df["Source de données utilisées enrichies"] = df.apply(normalize_and_enrich_sources, axis=1)
df["Domaines médicaux investigués"] = df["Domaines médicaux investigués"].apply(normalize_autres)
df["Statut"] = df["Etape  : Complétude"].apply(determine_status)
df["search_text"] = df.astype(str).apply(lambda x: " ".join(x).lower(), axis=1)

# ==================== COLONNES ET OPTIONS ====================
columns_display = ["Référence", "title", "Source de données utilisées enrichies",
                   "statut calendrier", "Domaines médicaux investigués",
                   "Finalité de l'étude", "Objectifs poursuivis",
                   "Responsable de traitement 1", "Responsable de traitement 2",
                   "Responsable de traitement 3", "Description Entité mettant à disposition"]

type_entite_options = ["Université", "Entreprise", "Etablissement public de santé", "Etablissement privé de santé",
                       "Association", "Bureau d'étude", "Industriel", "Start-up", "INSERM", "Fédération", "Agence"]

# ==================== EXTRACTION DES OPTIONS UNIQUES ====================
# Aires thérapeutiques
aires_set = set()
for val in df["Domaines médicaux investigués"].dropna():
    parts = re.split(r",", str(val))
    for p in parts:
        p_clean = clean_value(p)
        if p_clean:
            aires_set.add(p_clean)
aires_options = ["TOUT"] + sorted(aires_set)

# **NOUVEAU : Extraction des dates de début**
# Convertir la colonne "Date de début" en datetime
df["Date de début"] = pd.to_datetime(df["Date de début"], errors='coerce')

# Extraire les années uniques (en ignorant les valeurs NaT)
annees_debut = df["Date de début"].dropna().dt.year.unique()
annees_debut_options = ["TOUT"] + sorted([int(annee) for annee in annees_debut], reverse=True)

# Sources de données
sources_set = set()
for val in df["Source de données utilisées enrichies"].dropna():
    parts = re.split(r",", str(val))
    for p in parts:
        p_clean = clean_value(p)
        if p_clean:
            sources_set.add(p_clean)
source_donnees_options = ["TOUT"] + sorted(sources_set)

# Finalités
finalites_set = set()
for val in df["Finalité de l'étude"].dropna():
    parts = re.split(r",", str(val))
    for p in parts:
        p_clean = clean_value(p)
        if p_clean:
            finalites_set.add(p_clean)
finalites_options = ["TOUT"] + sorted(finalites_set)

# Objectifs
objectifs_set = set()
for val in df["Objectifs poursuivis"].dropna():
    parts = re.split(r",", str(val))
    for p in parts:
        p_clean = clean_value(p)
        if p_clean:
            objectifs_set.add(p_clean)
objectifs_options = ["TOUT"] + sorted(objectifs_set)

# Entités responsables
entites_responsables = pd.concat([
    df["Responsable de traitement 1"], 
    df["Responsable de traitement 2"], 
    df["Responsable de traitement 3"]
]).dropna().unique()
entites_options = sorted(entites_responsables)

# ==================== INITIALISATION DES ÉTATS ====================
if 'selected_types' not in st.session_state:
    st.session_state.selected_types = ["TOUT"]
if 'selected_aires' not in st.session_state:
    st.session_state.selected_aires = ["TOUT"]
if 'selected_sources' not in st.session_state:
    st.session_state.selected_sources = ["TOUT"]
if 'selected_finalites' not in st.session_state:
    st.session_state.selected_finalites = ["TOUT"]
if 'selected_objectifs' not in st.session_state:
    st.session_state.selected_objectifs = ["TOUT"]
if 'selected_annees' not in st.session_state:
    st.session_state.selected_annees = ["TOUT"]
if 'entite_search' not in st.session_state:
    st.session_state.entite_search = ""
if 'selected_entite_dropdown' not in st.session_state:
    st.session_state.selected_entite_dropdown = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = None
if 'show_article' not in st.session_state:
    st.session_state.show_article = False
if 'selected_article_index' not in st.session_state:
    st.session_state.selected_article_index = None

# ==================== FONCTION DE FILTRAGE ====================
def get_filtered_df(query_global, selected_types, selected_aires, selected_sources, 
                    selected_finalites, selected_objectifs, entite_responsable, 
                    selected_entite_dropdown, selected_annees, selected_status):
    """
    Filtre le DataFrame selon tous les critères sélectionnés
    """
    filtered_df = df.copy()

    # Filtre recherche globale
    if query_global:
        filtered_df = filtered_df[filtered_df["search_text"].str.contains(query_global.lower(), na=False)]

    # Filtre type d'entité
    if selected_types and "TOUT" not in selected_types:
        mask_type = False
        for col in ["Type responsable treatment 1", "Type responsable treatment 2", "Type responsable treatment 3"]:
            for t in selected_types:
                mask_type = mask_type | filtered_df[col].astype(str).str.lower().str.contains(t.lower(), na=False)
        filtered_df = filtered_df[mask_type]

    # Filtre aire thérapeutique
    if selected_aires and "TOUT" not in selected_aires:
        mask_aire = False
        for aire in selected_aires:
            mask_aire = mask_aire | filtered_df["Domaines médicaux investigués"].astype(str).str.lower().str.contains(aire.lower(), na=False)
        filtered_df = filtered_df[mask_aire]

    # Filtre finalité
    if selected_finalites and "TOUT" not in selected_finalites:
        mask_finalite = False
        for finalite in selected_finalites:
            mask_finalite = mask_finalite | filtered_df["Finalité de l'étude"].astype(str).str.lower().str.contains(finalite.lower(), na=False)
        filtered_df = filtered_df[mask_finalite]

    # Filtre objectifs
    if selected_objectifs and "TOUT" not in selected_objectifs:
        mask_objectif = False
        for objectif in selected_objectifs:
            mask_objectif = mask_objectif | filtered_df["Objectifs poursuivis"].astype(str).str.lower().str.contains(objectif.lower(), na=False)
        filtered_df = filtered_df[mask_objectif]

    # Filtre entité responsable (combinaison recherche textuelle + dropdown)
    if (entite_responsable and entite_responsable.strip() != "") or (selected_entite_dropdown and len(selected_entite_dropdown) > 0):
        mask_entite = False

        # Recherche textuelle
        if entite_responsable and entite_responsable.strip() != "":
            for col in ["Responsable de traitement 1", "Responsable de traitement 2", "Responsable de traitement 3"]:
                mask_entite = mask_entite | filtered_df[col].astype(str).str.lower().str.contains(entite_responsable.lower(), na=False)

        # Sélection dropdown
        if selected_entite_dropdown and len(selected_entite_dropdown) > 0:
            for entite in selected_entite_dropdown:
                for col in ["Responsable de traitement 1", "Responsable de traitement 2", "Responsable de traitement 3"]:
                    mask_entite = mask_entite | (filtered_df[col].astype(str) == entite)

        filtered_df = filtered_df[mask_entite]

    # Filtre date de début (année)
    if selected_annees and "TOUT" not in selected_annees:
        mask_annee = False
        for annee in selected_annees:
            mask_annee = mask_annee | (filtered_df["Date de début"].dt.year == annee)
        filtered_df = filtered_df[mask_annee]

    # Filtre source de données (avec gestion SNDS et HDH hiérarchique)
    if selected_sources and "TOUT" not in selected_sources:
        mask_source = False

        # Vérifier si SNDS est sélectionné (sans sous-composante)
        if "SNDS" in selected_sources:
            mask_source = mask_source | filtered_df["Source de données utilisées enrichies"].astype(str).str.contains("SNDS", na=False)

        # Vérifier si HDH est sélectionné (sans sous-base)
        if "HDH" in selected_sources:
            mask_source = mask_source | filtered_df["Source de données utilisées enrichies"].astype(str).str.contains("HDH", na=False)

        # Pour les autres sources spécifiques
        for s in selected_sources:
            if s != "SNDS" and s != "HDH":
                mask_source = mask_source | filtered_df["Source de données utilisées enrichies"].astype(str).str.lower().str.contains(re.escape(s.lower()), na=False)

        filtered_df = filtered_df[mask_source]

    # Filtre statut
    if selected_status != "TOUT":
        filtered_df = filtered_df[filtered_df["Statut"] == selected_status]

    return filtered_df
# ==================== INTERFACE UTILISATEUR ====================

# Section de recherche textuelle
st.markdown('<div class="sub-header">🔍 Recherche textuelle</div>', unsafe_allow_html=True)
query_global = st.text_input("Recherche globale dans toutes les colonnes", placeholder="Entrez un mot-clé...", key="search_global")

st.markdown("---")

# Section des filtres
st.markdown('<div class="sub-header">🎯 Filtres avancés</div>', unsafe_allow_html=True)

# Créer 3 colonnes pour les filtres
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown('<p class="filter-title">Type d\'entité</p>', unsafe_allow_html=True)
    selected_types = st.multiselect(
        "Type d'entité",
        options=["TOUT"] + type_entite_options,
        default=st.session_state.selected_types,
        key="types_filter",
        label_visibility="collapsed"
    )
    # Logique TOUT : si TOUT est sélectionné, désélectionner les autres
    if "TOUT" in selected_types and len(selected_types) > 1:
        selected_types = ["TOUT"]
    elif len(selected_types) == 0:
        selected_types = ["TOUT"]
    st.session_state.selected_types = selected_types

    # Espacement visuel
    st.markdown("<br>", unsafe_allow_html=True)

    # **Entité responsable avec recherche textuelle ET dropdown**
    st.markdown('<p class="filter-title">Entité responsable</p>', unsafe_allow_html=True)

    # Recherche textuelle
    entite_responsable = st.text_input(
        "Recherche textuelle",
        value=st.session_state.entite_search,
        placeholder="Tapez pour rechercher...",
        key="entite_filter_text",
        label_visibility="collapsed",
        help="Recherche par mot-clé dans les entités"
    )
    st.session_state.entite_search = entite_responsable

    # Dropdown de sélection
    selected_entite_dropdown = st.multiselect(
        "Sélection directe",
        options=entites_options,
        default=st.session_state.selected_entite_dropdown,
        key="entite_filter_dropdown",
        label_visibility="collapsed",
        help="Sélectionnez une ou plusieurs entités"
    )
    st.session_state.selected_entite_dropdown = selected_entite_dropdown

with col2:
    st.markdown('<p class="filter-title">Aire thérapeutique</p>', unsafe_allow_html=True)
    selected_aires = st.multiselect(
        "Aire thérapeutique",
        options=aires_options,
        default=st.session_state.selected_aires,
        key="aires_filter",
        label_visibility="collapsed"
    )
    # Logique TOUT pour aires thérapeutiques
    if "TOUT" in selected_aires and len(selected_aires) > 1:
        selected_aires = ["TOUT"]
    elif len(selected_aires) == 0:
        selected_aires = ["TOUT"]
    st.session_state.selected_aires = selected_aires

    # Espacement visuel
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<p class="filter-title">Finalité de l\'étude</p>', unsafe_allow_html=True)
    selected_finalites = st.multiselect(
        "Finalité de l'étude",
        options=finalites_options,
        default=st.session_state.selected_finalites,
        key="finalites_filter",
        label_visibility="collapsed"
    )
    # Logique TOUT pour finalités
    if "TOUT" in selected_finalites and len(selected_finalites) > 1:
        selected_finalites = ["TOUT"]
    elif len(selected_finalites) == 0:
        selected_finalites = ["TOUT"]
    st.session_state.selected_finalites = selected_finalites

    # Espacement visuel
    st.markdown("<br>", unsafe_allow_html=True)

    # **Filtre année de début**
    st.markdown('<p class="filter-title">Année de début</p>', unsafe_allow_html=True)
    selected_annees = st.multiselect(
        "Année de début",
        options=annees_debut_options,
        default=st.session_state.selected_annees,
        key="annees_filter",
        label_visibility="collapsed"
    )
    if "TOUT" in selected_annees and len(selected_annees) > 1:
        selected_annees = ["TOUT"]
    elif len(selected_annees) == 0:
        selected_annees = ["TOUT"]
    st.session_state.selected_annees = selected_annees

with col3:
    st.markdown('<p class="filter-title">Objectifs poursuivis</p>', unsafe_allow_html=True)
    selected_objectifs = st.multiselect(
        "Objectifs poursuivis",
        options=objectifs_options,
        default=st.session_state.selected_objectifs,
        key="objectifs_filter",
        label_visibility="collapsed"
    )
    # Logique TOUT pour objectifs
    if "TOUT" in selected_objectifs and len(selected_objectifs) > 1:
        selected_objectifs = ["TOUT"]
    elif len(selected_objectifs) == 0:
        selected_objectifs = ["TOUT"]
    st.session_state.selected_objectifs = selected_objectifs

    # Espacement visuel
    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<p class="filter-title">Source de données</p>', unsafe_allow_html=True)
    selected_sources = st.multiselect(
        "Source de données",
        options=source_donnees_options,
        default=st.session_state.selected_sources,
        key="sources_filter",
        label_visibility="collapsed"
    )
    # Logique TOUT pour sources
    if "TOUT" in selected_sources and len(selected_sources) > 1:
        selected_sources = ["TOUT"]
    elif len(selected_sources) == 0:
        selected_sources = ["TOUT"]
    st.session_state.selected_sources = selected_sources

    # Espacement visuel
    st.markdown("<br>", unsafe_allow_html=True)

    # **Filtre Statut**
    st.markdown('<p class="filter-title">Statut</p>', unsafe_allow_html=True)
    selected_status = st.selectbox(
        "Statut",
        options=["TOUT", "En cours", "Terminé"],
        key="status_filter",
        label_visibility="collapsed"
    )

st.markdown("---")

# ==================== BOUTONS D'ACTION ====================
col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)

with col_btn1:
    if st.button("🔍 Rechercher", type="primary", use_container_width=True):
        filtered_df = get_filtered_df(
            query_global, selected_types, selected_aires, selected_sources,
            selected_finalites, selected_objectifs, entite_responsable, 
            selected_entite_dropdown, selected_annees, selected_status
        )
        st.session_state.current_results = filtered_df
        st.session_state.show_article = False

with col_btn2:
    if st.button("🔄 Réinitialiser", use_container_width=True):
        # Réinitialiser TOUS les filtres et états
        st.session_state.selected_types = ["TOUT"]
        st.session_state.selected_aires = ["TOUT"]
        st.session_state.selected_sources = ["TOUT"]
        st.session_state.selected_finalites = ["TOUT"]
        st.session_state.selected_objectifs = ["TOUT"]
        st.session_state.selected_annees = ["TOUT"]
        st.session_state.entite_search = ""
        st.session_state.selected_entite_dropdown = []
        st.session_state.current_results = None
        st.session_state.show_article = False
        st.session_state.selected_article_index = None
        
        # Réinitialiser aussi les clés des widgets pour forcer leur mise à jour
        for key in list(st.session_state.keys()):
            if key.endswith('_filter') or key == 'search_global' or key == 'entite_filter_text' or key == 'entite_filter_dropdown' or key == 'status_filter':
                del st.session_state[key]
        
        # Forcer le rechargement de la page
        st.rerun()

with col_btn3:
    if st.button("📊 Afficher tout", use_container_width=True):
        # Réinitialiser tous les filtres et afficher tous les résultats
        st.session_state.selected_types = ["TOUT"]
        st.session_state.selected_aires = ["TOUT"]
        st.session_state.selected_sources = ["TOUT"]
        st.session_state.selected_finalites = ["TOUT"]
        st.session_state.selected_objectifs = ["TOUT"]
        st.session_state.selected_annees = ["TOUT"]
        st.session_state.entite_search = ""
        st.session_state.selected_entite_dropdown = []
        st.session_state.current_results = df
        st.session_state.show_article = False

with col_btn4:
    if st.session_state.current_results is not None and not st.session_state.current_results.empty:
        # Fonction pour créer le fichier Excel en mémoire
        def create_excel_download():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                st.session_state.current_results.to_excel(writer, index=False, sheet_name='Résultats')
            output.seek(0)
            return output.getvalue()

        excel_data = create_excel_download()
        st.download_button(
            label="📥 Exporter Excel",
            data=excel_data,
            file_name="resultats_filtrés.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        # Bouton désactivé si aucun résultat
        st.button("📥 Aucun résultat", disabled=True, use_container_width=True)

st.markdown("---")

# ==================== AFFICHAGE DES CRITÈRES ACTIFS ====================
# Afficher les critères de filtrage actuellement actifs
criteria_active = []

if query_global:
    criteria_active.append(f"**Recherche textuelle:** {query_global}")

if selected_types != ["TOUT"]:
    criteria_active.append(f"**Type d'entité:** {', '.join(selected_types)}")

if entite_responsable:
    criteria_active.append(f"**Entité responsable (recherche):** {entite_responsable}")

if selected_entite_dropdown:
    criteria_active.append(f"**Entités sélectionnées:** {', '.join(selected_entite_dropdown)}")

if selected_aires != ["TOUT"]:
    criteria_active.append(f"**Aire thérapeutique:** {', '.join(selected_aires)}")

if selected_sources != ["TOUT"]:
    criteria_active.append(f"**Sources de données:** {', '.join(selected_sources)}")

if selected_finalites != ["TOUT"]:
    criteria_active.append(f"**Finalités:** {', '.join(selected_finalites)}")

if selected_objectifs != ["TOUT"]:
    criteria_active.append(f"**Objectifs:** {', '.join(selected_objectifs)}")

if selected_annees != ["TOUT"]:
    criteria_active.append(f"**Années de début:** {', '.join([str(a) for a in selected_annees])}")

if selected_status != "TOUT":
    criteria_active.append(f"**Statut:** {selected_status}")

if criteria_active:
    with st.expander("🎯 Critères de filtrage actifs", expanded=False):
        for criteria in criteria_active:
            st.write(f"• {criteria}")
else:
    st.info("ℹ️ Aucun filtre actif - Tous les projets seront affichés lors de la recherche")

# ==================== AFFICHAGE DES RÉSULTATS ====================
if st.session_state.current_results is not None:
    num_results = len(st.session_state.current_results)

    # Métriques des résultats avec couleurs améliorées
    col_metric1, col_metric2, col_metric3 = st.columns(3)

    with col_metric1:
        st.metric("📊 Résultats trouvés", num_results)

    with col_metric2:
        if num_results > 0:
            en_cours = len(st.session_state.current_results[st.session_state.current_results["Statut"] == "En cours"])
            st.metric("🔄 Projets en cours", en_cours)

    with col_metric3:
        if num_results > 0:
            termines = len(st.session_state.current_results[st.session_state.current_results["Statut"] == "Terminé"])
            st.metric("✅ Projets terminés", termines)

    if num_results > 0:
        st.markdown("### 📋 Tableau des résultats")

        # Afficher le DataFrame avec les colonnes sélectionnées
        display_df = st.session_state.current_results[columns_display].copy()

        # Configurer l'affichage du dataframe avec hauteur fixe
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=400,  # Hauteur fixe pour éviter les très longs tableaux
            column_config={
                "Référence": st.column_config.TextColumn("Référence", width="small"),
                "title": st.column_config.TextColumn("Titre", width="large"),
                "Source de données utilisées enrichies": st.column_config.TextColumn("Sources", width="medium"),
                "statut calendrier": st.column_config.TextColumn("Statut calendrier", width="small"),
                "Domaines médicaux investigués": st.column_config.TextColumn("Domaines médicaux", width="medium")
            }
        )

        # ==================== VISUALISATION D'UN ARTICLE ====================
        st.markdown("---")
        st.markdown("### 👁️ Visualiser un article en détail")

        # Sélection de l'article à visualiser
        references = st.session_state.current_results["Référence"].tolist()

        col_select, col_action = st.columns([3, 1])

        with col_select:
            selected_reference = st.selectbox(
                "Sélectionnez un article par sa référence",
                options=["Sélectionner un article..."] + references,
                key="article_selector"
            )

        with col_action:
            if selected_reference and selected_reference != "Sélectionner un article...":
                if st.button("👁️ Visualiser", type="primary", use_container_width=True):
                    st.session_state.show_article = True
                    st.session_state.selected_article_index = selected_reference
                    st.rerun()

        # Affichage de l'article sélectionné
        if st.session_state.show_article and st.session_state.selected_article_index:
            try:
                article_row = st.session_state.current_results[
                    st.session_state.current_results["Référence"] == st.session_state.selected_article_index
                ].iloc[0]

                st.markdown("---")

                # En-tête de l'article avec bouton fermer
                col_title, col_close = st.columns([4, 1])

                with col_title:
                    st.markdown(f"## 📄 Détails de l'article - {st.session_state.selected_article_index}")

                with col_close:
                    if st.button("❌ Fermer", use_container_width=True):
                        st.session_state.show_article = False
                        st.session_state.selected_article_index = None
                        st.rerun()

                # Conteneur avec barre de défilement
                with st.container():
                    # Afficher toutes les colonnes du DataFrame
                    all_columns = list(df.columns)

                    for col in all_columns:
                        if col in article_row.index:
                            # Titre du champ (en rouge)
                            st.markdown(f'<div class="article-field-label">{col}</div>', unsafe_allow_html=True)

                            # Valeur du champ
                            value = article_row[col]

                            # Vérifier si la valeur est vide ou NaN
                            if pd.isna(value) or str(value).strip() == "" or str(value).lower() == "nan":
                                st.markdown('<div class="article-field-empty">Donnée non renseignée</div>', unsafe_allow_html=True)
                            else:
                                display_value = str(value)
                                # Utiliser un fond légèrement coloré pour améliorer la lisibilité
                                st.markdown(f'<div class="article-field-value">{display_value}</div>', unsafe_allow_html=True)

                            # Ligne de séparation
                            st.markdown("---")

            except IndexError:
                st.error("❌ Article non trouvé dans les résultats.")
            except Exception as e:
                st.error(f"❌ Erreur lors de l'affichage de l'article : {e}")

    else:
        st.info("ℹ️ Aucun résultat trouvé avec les critères sélectionnés.")

        # Suggestions pour améliorer la recherche
        with st.expander("💡 Conseils pour améliorer votre recherche", expanded=False):
            st.write("• Essayez de réduire le nombre de filtres appliqués")
            st.write("• Vérifiez l'orthographe de vos termes de recherche")
            st.write("• Utilisez des mots-clés plus généraux")
            st.write("• Cliquez sur 'Afficher tout' pour voir tous les projets disponibles")

else:
    # Message d'accueil quand aucune recherche n'a été effectuée
    st.info("👆 Utilisez les filtres ci-dessus et cliquez sur 'Rechercher' pour afficher les résultats.")

    # Statistiques générales de la base de données
    col_stat1, col_stat2, col_stat3 = st.columns(3)

    with col_stat1:
        st.metric("📊 Total des projets", len(df))

    with col_stat2:
        en_cours_total = len(df[df["Statut"] == "En cours"])
        st.metric("🔄 Projets en cours", en_cours_total)

    with col_stat3:
        termines_total = len(df[df["Statut"] == "Terminé"])
        st.metric("✅ Projets terminés", termines_total)

# ==================== FOOTER ====================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p><strong>Moteur de recherche des projets HDH</strong> | Développé avec Streamlit</p>
    <p style='font-size: 0.8rem;'>Compatible avec les thèmes clair et sombre</p>
</div>
""", unsafe_allow_html=True)


