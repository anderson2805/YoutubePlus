import warnings

warnings.filterwarnings("ignore")

import streamlit as st
from keybert import KeyBERT
from keyphrase_vectorizers import KeyphraseCountVectorizer
from sentence_transformers import SentenceTransformer

try:
    en_model = SentenceTransformer("./model/all-mpnet-base-v2")
except:
    en_model = SentenceTransformer("./model/all-MiniLM-L6-v2")


@st.cache(suppress_st_warning=True)
def extractKeywords(doc: str) -> list:
    vectorizer = KeyphraseCountVectorizer()
    kw_model = KeyBERT(model=en_model)

    keywords = kw_model.extract_keywords(doc, vectorizer=vectorizer, use_mmr = True)
    return [item[0] for item in keywords]
