import warnings
warnings.filterwarnings("ignore")

from keybert import KeyBERT
from keyphrase_vectorizers import KeyphraseCountVectorizer
from sentence_transformers import SentenceTransformer



en_model = SentenceTransformer("all-MiniLM-L12-v2")

def extractKeywords(doc: str) -> list:

    vectorizer = KeyphraseCountVectorizer()
    kw_model = KeyBERT(model=en_model)

    keywords = kw_model.extract_keywords(doc, vectorizer=vectorizer, use_mmr = True)
    return [item[0] for item in keywords]
# 