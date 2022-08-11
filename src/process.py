import re
from datetime import datetime
from typing import List

import pandas as pd
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit as st

from src.ingestion import getVideoDetail


def searchChunking(ids: List):
    resultsChunks = [ids[i:i + 50]
                     for i in range(0, len(ids), 50)]
    return resultsChunks

#@st.experimental_memo
def process_description(text):
    if (text == ""):
        return ""
    sentences = re.sub(r'(\W)(?=\1)', '', text).split('\n')
    processed = []
    for index, sentence in enumerate(sentences):
        url_search = re.search(r'http\S+', sentence)
        at_search = re.search(r'@', sentence)
        if(re.subn(r'\W', '', sentence)[1] == len(sentence) or not sentence[0].isalpha()):
            break
        elif (url_search is None and at_search is None):
            processed.append(sentence)
        elif(len(processed) > 1 and (url_search is not None and (url_search.span()[1] - url_search.span()[0]) == len(sentence)) or sentences[index - 1][-1] in [':', '-']):
            try:
                processed.pop()
            except:
                print(processed)
    return " ".join(processed)


def durationSec(durationLs):
    durationLs = [int(time) for time in durationLs]
    if(len(durationLs) == 3):
        return (durationLs[0] * 3600) + (durationLs[1] * 60) + durationLs[2]
    elif(len(durationLs) == 2):
        return (durationLs[0] * 60) + durationLs[1]
    else:
        return durationLs[0]

#@st.experimental_memo
def extract_hashtags(text):
    # the regular expression
    regex = "#(\w+)"
    # extracting the hashtags
    hashtag_list = re.findall(regex, text)
    hashtag_list = [hashtag.title() for hashtag in hashtag_list]
    return(hashtag_list)

#@st.experimental_memo
def process_captions(transcriptdict):
    preprocess_captions = ""
    for line in transcriptdict:
        preprocess_captions += " " + line['text']
    removed_descriptive = re.sub(
        " [\(\[].*?[\)\]]", "", preprocess_captions)
    output = re.sub(r'\b(\w+) \1\b', r'\1',
                    removed_descriptive, flags=re.IGNORECASE)
    output = output.replace("\n", " ").replace(u'\xa0', u' ')
    output = re.sub(' +',' ', output)
    return output[1:]

#@st.experimental_singleton
def processVideoIds(videoIds: List):
    videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList = [], [], [], [], []
    processBar = st.progress(0)
    chunkList = searchChunking(videoIds)
    chunkLength = len(chunkList)
    for count, chunk in enumerate(chunkList):
        print("Processing videos %i / %i" %
              (count + 1, chunkLength))
        processBar.progress((count+1)/chunkLength)
        videoIds_chunk = ",".join(chunk)
        response = getVideoDetail(videoIds_chunk)

        for item in response['items']:
            contentDetails = item['contentDetails']
            snippet = item['snippet']
            statistics = item.get('statistics')
            topicDetails = item.get('topicDetails')
            recordingDetails = item.get('recordingDetails')
            recordingDate = recordingDetails.get('recordingDate')
            hashtags = extract_hashtags(snippet.get('description'))

            videoDict = {'videoId': item['id'],
                         'publishedAt': (snippet['publishedAt']),
                         'recordingDate': recordingDate,
                         'collectDateTime': datetime.now(),
                         'title': snippet['title'],
                         'description': snippet.get('description'),
                         'processedDescription': process_description(snippet.get('description',"")),
                         'duration': durationSec(re.findall(r'\d+', contentDetails['duration'])),
                         'defaultAudioLanguage': snippet.get('defaultAudioLanguage'),
                         'tags': str(snippet.get('tags')),
                         'commentCount': statistics.get('commentCount'),
                         'favoriteCount': statistics['favoriteCount'],
                         'likeCount': statistics.get('likeCount'),
                         'viewCount': statistics.get('viewCount'),
                         'channelId': snippet['channelId']}
            videoList.append(videoDict)

            if topicDetails:
                for topic in topicDetails['topicCategories']:
                    topicDict = {'videoId': item['id'],
                                 'topics': topic.split('/')[-1]}
                    videoTopicsList.append(topicDict)

            if (recordingDetails.get('locationDescription') is not None):
                videoLocDict = {'videoId': item['id'],
                                'locationDescription': recordingDetails.get('locationDescription')}
                videoLocList.append(videoLocDict)

            if (len(hashtags) != 0):
                for hashtag in hashtags:
                    videoHashtagsDict = {'videoId': item['id'],
                                         'hashtags': hashtag}
                    videoHashtagsList.append(videoHashtagsDict)

            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(
                    item['id'])
                # iterate over all available transcripts
                for index, transcript in enumerate(transcript_list):
                    if(index == 0):
                        caption = process_captions(transcript.fetch())
                        lang = transcript.language
                        translatedCaption = None
                        embedding = caption
                    if(index == 0 and 'English' not in transcript.language):
                        translatedCaption = process_captions(
                            transcript.translate('en').fetch())
                        embedding = translatedCaption
                videoCaptionDict = {'videoId': item['id'],
                                    'caption': caption,
                                    'lang': lang,
                                    'translatedCaption': translatedCaption,
                                    'embedding': embedding}
                videoCaptionList.append(videoCaptionDict)
            except:
                next
    processBar.empty()
    return videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList


def videoDetails_df(videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList):
    allDf = {}
    videoDf = pd.DataFrame(videoList)
    videoDf = videoDf.set_index("videoId")
    allDf['videoDf'] = videoDf
    allDf['videoLocDf'] = pd.DataFrame()
    allDf['videoHashtagsDf'] = pd.DataFrame()
    allDf['videoCaptionDf'] = pd.DataFrame()
    allDf['videoTopicsList'] = pd.DataFrame()
    if len(videoLocList) != 0:
        videoLocDf = pd.DataFrame(videoLocList)
        videoLocDf = videoLocDf.set_index("videoId")
        allDf['videoLocDf'] = videoLocDf

    if len(videoHashtagsList) != 0:
        videoHashtagsDf = pd.DataFrame(videoHashtagsList)
        videoHashtagsDf = videoHashtagsDf.set_index("videoId")
        allDf['videoHashtagsDf'] = videoHashtagsDf

    if len(videoCaptionList) != 0:
        videoCaptionDf = pd.DataFrame(videoCaptionList)
        videoCaptionDf = videoCaptionDf.set_index("videoId")
        allDf['videoCaptionDf'] = videoCaptionDf

    if len(videoTopicsList) != 0:
        videoTopicsDf = pd.DataFrame(videoTopicsList)
        videoTopicsDf = videoTopicsDf.set_index("videoId")
        allDf['videoTopicsDf'] = videoTopicsDf
    return allDf
