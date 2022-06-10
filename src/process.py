import re
from datetime import datetime
from typing import List

import numpy as np
import pandas as pd
from dateutil import parser, tz
from youtube_transcript_api import YouTubeTranscriptApi

from src.ingestion import getVideoDetail

to_zone = tz.tzlocal()

from src.semantic_similarity import embed

def searchChunking(ids: List):
    resultsChunks = [ids[i:i + 50]
                     for i in range(0, len(ids), 50)]
    return resultsChunks



def process_description(text):
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
            processed.pop()
    return " ".join(processed)


def durationSec(durationLs):
    durationLs = [int(time) for time in durationLs]
    if(len(durationLs) == 3):
        return (durationLs[0] * 3600) + (durationLs[1] * 60) + durationLs[2]
    elif(len(durationLs) == 2):
        return (durationLs[0] * 60) + durationLs[1]
    else:
        return durationLs[0]


def extract_hashtags(text):
    # the regular expression
    regex = "#(\w+)"
    # extracting the hashtags
    hashtag_list = re.findall(regex, text)
    return(hashtag_list)


def process_captions(transcriptdict):
    preprocess_captions = ""
    for line in transcriptdict:
        preprocess_captions += " " + line['text']
    removed_descriptive = re.sub(
        " [\(\[].*?[\)\]]", "", preprocess_captions)
    output = re.sub(r'\b(\w+) \1\b', r'\1',
                    removed_descriptive, flags=re.IGNORECASE)
    return output


def processVideoIds(videoIds: List):
    videoList, videoLocList, videoHashtagsList, videoCaptionList = [], [], [], []
    for count, chunk in enumerate(searchChunking(videoIds)):
        print("Processing videos %i / %i"%(count + 1, len(searchChunking(videoIds))))
        videoIds_chunk = ",".join(chunk)
        response = getVideoDetail(videoIds_chunk)

        for item in response['items']:
            contentDetails = item['contentDetails']
            snippet = item['snippet']
            statistics = item.get('statistics')
            topicDetails = item.get('topicDetails')
            recordingDetails = item.get('recordingDetails')
            if (recordingDetails.get('recordingDate') is not None):
                recordingDate = parser.parse(recordingDetails.get(
                    'recordingDate'))
            else:
                recordingDate = None
            hashtags = extract_hashtags(snippet.get('description'))

            videoDict = {'videoId': item['id'],
                         'publishedAt': (snippet['publishedAt']),
                         'recordingDate': recordingDate,
                         'collectDateTime': datetime.now(),
                         'title': snippet['title'],
                         'description': snippet.get('description'),
                         'processedDescription': process_description(snippet.get('description')),
                         'duration': durationSec(re.findall(r'\d+', contentDetails['duration'])),
                         'defaultAudioLanguage': snippet.get('defaultAudioLanguage'),
                         'tags': str(snippet.get('tags')),
                         'topicCategories': str([(topic.split('/')[-1]) for topic in topicDetails['topicCategories']]) if topicDetails else None,
                         'commentCount': statistics.get('commentCount'),
                         'favoriteCount': statistics['favoriteCount'],
                         'likeCount': statistics.get('likeCount'),
                         'viewCount': statistics.get('viewCount'),
                         'channelId': snippet['channelId']}
            videoList.append(videoDict)

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
                transcript_list = YouTubeTranscriptApi.list_transcripts(item['id'])
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


    return videoList, videoLocList, videoHashtagsList, videoCaptionList

def videoDetails_df(videoList, videoLocList, videoHashtagsList, videoCaptionList):
    allDf = {}
    videoDf = pd.DataFrame(videoList)
    videoDf = videoDf.set_index("videoId")
    allDf['videoDf'] = videoDf
    allDf['videoLocDf'] = pd.DataFrame()
    allDf['videoHashtagsDf'] = pd.DataFrame()
    allDf['videoCaptionDf'] = pd.DataFrame()

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
    return allDf
