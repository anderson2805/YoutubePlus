import streamlit as st
import numpy as np
import sentencepiece as spm
import tensorflow.compat.v1 as tf
import tensorflow_hub as hub

tf.disable_eager_execution()





sp = spm.SentencePieceProcessor()
spm_path = './model/universal_encoder_8k_spm.model'
with tf.io.gfile.GFile(spm_path, mode="rb") as f:
    sp.LoadFromSerializedProto(f.read())
print("SentencePiece model loaded at {}.".format(spm_path))

# g = tf.Graph()
# with g.as_default():
#     input_placeholder = tf.sparse_placeholder(tf.int64, shape=[None, None])
#     module = hub.Module(
#     "https://tfhub.dev/google/universal-sentence-encoder-lite/2")

# g.finalize() # not mandatory, but a nice practice, especially in multithreaded environment
@st.cache(suppress_st_warning=True)
def process_to_IDs_in_sparse_format(sp, sentences):
    # An utility method that processes sentences with the sentence piece processor
    # 'sp' and returns the results in tf.SparseTensor-similar format:
    # (values, indices, dense_shape)
    ids = [sp.EncodeAsIds(x) for x in sentences]
    max_len = max(len(x) for x in ids)
    dense_shape = (len(ids), max_len)
    values = [item for sublist in ids for item in sublist]
    indices = [[row, col]
               for row in range(len(ids)) for col in range(len(ids[row]))]
    return (values, indices, dense_shape)

# Compute a representation for each message, showing various lengths supported.

@st.cache(suppress_st_warning=True)
def embed(doc):
    g = tf.Graph()
    with g.as_default():
        input_placeholder = tf.sparse_placeholder(tf.int64, shape=[None, None])
        module = hub.Module(
            "./models/universal-sentence-encoder-lite_2")
            
        encodings = module(
        inputs=dict(
            values=input_placeholder.values,
            indices=input_placeholder.indices,
            dense_shape=input_placeholder.dense_shape))

        messages = doc
        with tf.Session(graph=g) as session:
            session.run(tf.global_variables_initializer())
            session.run(tf.tables_initializer())
            values, indices, dense_shape = process_to_IDs_in_sparse_format(
                sp, messages)

            message_embeddings = session.run(
                encodings,
                feed_dict={input_placeholder.values: values,
                            input_placeholder.indices: indices,
                            input_placeholder.dense_shape: dense_shape})


    g.finalize()  # not mandatory, but a nice practice, especially in multithreaded environment

    return np.array(message_embeddings).tolist()
