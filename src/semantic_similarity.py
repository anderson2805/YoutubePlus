import streamlit as st
import numpy as np
import sentencepiece as spm
import os
import tensorflow_hub as hub

import tensorflow as tf
# @param ["https://tfhub.dev/google/universal-sentence-encoder/4", "https://tfhub.dev/google/universal-sentence-encoder-large/5"]
module_url = "./model/universal-sentence-encoder/4"
model = hub.load(module_url)

print('Full Universal sentences encoder(v4) loaded...')

@st.cache(suppress_st_warning=False)
def embed(doc):
    return model(doc).numpy().tolist()