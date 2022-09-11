import re
from datetime import datetime
from typing import List

import pandas as pd
from youtube_transcript_api import YouTubeTranscriptApi
import streamlit as st

from src.ingestion import getChannelDetail, getVideoDetail, getCommentDetail

def searchChunking(ids: List, size: int = 50):
    resultsChunks = [ids[i:i + size]
                     for i in range(0, len(ids), size)]
    return resultsChunks

# @st.experimental_memo


def process_description(text):
    if (text == ""):
        return ""
    sentences = re.sub(r'(\W)(?=\1)', '', text).split('\n')
    processed = []
    for index, sentence in enumerate(sentences):
        url_search = re.search(r'http\S+', sentence)
        at_search = re.search(r'@', sentence)
        if(re.subn(r'\W', '', sentence)[1] == len(sentence) or not sentence[0].isalpha() or len(sentences[index-1]) == 0):
            break
        elif (url_search is None and at_search is None):
            processed.append(sentence)
        elif(len(processed) > 1 and (url_search is not None and len(url_search.span()) > 1 and (url_search.span()[1] - url_search.span()[0]) == len(sentence)) or sentences[index - 1][-1] in [':', '-']):
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

# @st.experimental_memo


def extract_hashtags(text):
    # the regular expression
    regex = "#(\w+)"
    # extracting the hashtags
    hashtag_list = re.findall(regex, text)
    hashtag_list = [hashtag.title() for hashtag in hashtag_list]
    return(hashtag_list)

# @st.experimental_memo


def process_captions(transcriptdict):
    preprocess_captions = ""
    for line in transcriptdict:
        preprocess_captions += " " + line['text']
    removed_descriptive = re.sub(
        " [\(\[].*?[\)\]]", "", preprocess_captions)
    output = re.sub(r'\b(\w+) \1\b', r'\1',
                    removed_descriptive, flags=re.IGNORECASE)
    output = output.replace("\n", " ").replace(u'\xa0', u' ')
    output = re.sub(' +', ' ', output)
    return output[1:]

# @st.experimental_singleton
def getLink(text: str):
    raw_urls = re.findall(r'href=[\'"]?([^\'" >]+)', text)
    return raw_urls

def cleanLink(url: str):
    hashtag = url.replace('http://www.youtube.com/results?search_query=%23','')
    cleaned_url = None
    if(len(hashtag)==len(url)):
        cleaned_url = url.replace('https://www.youtube.com/watch?v=', 'https://youtu.be/').split('&',1)[0].split('?',1)[0]
        hashtag = None
 
    return pd.Series([cleaned_url, hashtag])

def processVideoIds(videoIds: List):
    videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList = [], [], [], [], [], []
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
            tags = snippet.get('tags', [])
            videoDict = {'videoId': item['id'],
                         'publishedAt': (snippet['publishedAt']),
                         'recordingDate': recordingDate,
                         'collectDateTime': datetime.now(),
                         'title': snippet['title'],
                         'description': snippet.get('description'),
                         'processedDescription': process_description(snippet.get('description', "")),
                         'duration': durationSec(re.findall(r'\d+', contentDetails['duration'])),
                         'defaultAudioLanguage': snippet.get('defaultAudioLanguage'),
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

            if (len(tags) != 0):
                for tag in tags:
                    videotagsDict = {'videoId': item['id'],
                                     'tag': tag}
                    videoTagsList.append(videotagsDict)

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
    return videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList


def videoDetails_df(videoList, videoLocList, videoHashtagsList, videoCaptionList, videoTopicsList, videoTagsList):
    allDf = {}
    videoDf = pd.DataFrame(videoList)
    videoDf = videoDf.set_index("videoId")
    allDf['videoDf'] = videoDf
    allDf['videoLocDf'] = pd.DataFrame()
    allDf['videoHashtagsDf'] = pd.DataFrame()
    allDf['videoCaptionDf'] = pd.DataFrame()
    allDf['videoTopicsList'] = pd.DataFrame()
    allDf['videoTagsDf'] = pd.DataFrame()
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

    if len(videoTagsList) != 0:
        videoTagsDf = pd.DataFrame(videoTagsList)
        videoTagsDf = videoTagsDf.set_index("videoId")
        allDf['videoTagsDf'] = videoTagsDf
    return allDf


def processChannelIds(channelIds: List):
    channelsList, channelTopicsList, localizationsList = [], [], []
    processBar = st.progress(0)
    chunkList = searchChunking(channelIds)
    chunkLength = len(chunkList)
    for count, chunk in enumerate(chunkList):
        print("Processing channels info %i / %i" %
              (count + 1, chunkLength))
        processBar.progress((count+1)/chunkLength)
        channelIds_chunk = ",".join(chunk)
        response = getChannelDetail(channelIds_chunk)
        for item in response['items']:
            snippet = item['snippet']
            statistics = item.get('statistics')
            topicDetails = item.get('topicDetails')
            localizations = item.get('localizations')
            brandSettings = item.get('brandingSettings',{})

            channelDict = {'channelId': item['id'],
                           'Channel Name': snippet.get('title'),
                           'description': snippet.get('description'),
                           'Creation Date': snippet.get('publishedAt'),
                           'defaultLanguage': snippet.get('defaultLanguage'),
                           'country': brandSettings.get('channel',{}).get('country'),
                           'viewCount': statistics.get('viewCount'),
                           'Subscribers': statistics.get('subscriberCount'),
                           'videoCount': statistics.get('videoCount'),
                           'trackingAccountId': brandSettings.get('channel',{}).get('trackingAnalyticsAccountId'),
                           }

            channelsList.append(channelDict)
            if topicDetails:
                for topic in topicDetails['topicCategories']:
                    topicDict = {'channelId': item['id'],
                                 'topics': topic.split('/')[-1]}
                    channelTopicsList.append(topicDict)
            if localizations:
                for key in localizations.keys():
                    localeDict = {'channelId': item['id'],
                                  'locale': key,
                                  'title': localizations[key].get('title'),
                                  'description': localizations[key].get('description')}
                    localizationsList.append(localeDict)

        channelDfDict = {'channelInfo': pd.DataFrame(channelsList)}
        if(channelTopicsList != []):
            channelDfDict.update(
                {'channelTopics': pd.DataFrame(channelTopicsList)})
        if(localizationsList != []):
            channelDfDict.update(
                {'channelLocale': pd.DataFrame(localizationsList)})
    return channelDfDict

def processVideosComments(videoIds: list):
    commentsResponses = []
    for videoId in videoIds:
        commentsResponses += getCommentDetail(videoId)
    return processComments(commentsResponses)

def processComments(commentsResponses):
    resultsDfs = {}
    commentsList = [{'commentId': comment.get('id'),
                    'videoId': comment['snippet']['videoId'],
                     'textDisplay': comment['snippet']['topLevelComment']['snippet']['textDisplay'],
                     'textOriginal': comment['snippet']['topLevelComment']['snippet']['textOriginal'],
                     'authorDisplayName': comment['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                     'authorChannelId': comment['snippet']['topLevelComment']['snippet']['authorChannelId']['value'],
                     'likeCount': comment['snippet']['topLevelComment']['snippet'].get('likeCount'),
                     'publishedAt': comment['snippet']['topLevelComment']['snippet'].get('publishedAt'),
                     'updatedAt': comment['snippet']['topLevelComment']['snippet'].get('updatedAt')} for comment in commentsResponses]
    commentsDf = pd.DataFrame(commentsList)
    authorInfoDf = processChannelIds(
        commentsDf['authorChannelId'].unique())['channelInfo']
    commentsProcessedDf = pd.merge(commentsDf, authorInfoDf[[
                                   'channelId', 'Creation Date']], left_on='authorChannelId', right_on='channelId').drop_duplicates(ignore_index = True)
    commentsProcessedDf[['publishedAt', 'updatedAt', 'Creation Date']] = commentsProcessedDf[[
        'publishedAt', 'updatedAt', 'Creation Date']].apply(pd.to_datetime).apply(lambda x: x.dt.tz_convert('Singapore')).apply(lambda x: x.dt.tz_localize(None))
    commentsProcessedDf['Account age when commenting (days)'] = (
        commentsProcessedDf['publishedAt'] - commentsProcessedDf['Creation Date']).dt.days
    commentsProcessedDf = commentsProcessedDf.join(commentsProcessedDf[['authorChannelId', 'videoId', 'commentId', 'likeCount']].groupby(by='authorChannelId').agg(
        No_Unique_Videos = ('videoId', 'nunique'), No_Comments_Made=('commentId', 'count'), Total_Likes=('likeCount', 'sum')), on='authorChannelId')
    commentsProcessedDf.drop(columns = 'channelId', axis = 1, inplace=True)
    resultsDfs.update(
        {'Comments': commentsProcessedDf,
         'Comments Author': authorInfoDf})
    linksDf = commentsDf[['commentId']].join(
        commentsDf.textDisplay.apply(getLink).explode().rename('rawLink')).dropna()
    if(len(linksDf) != 0):
        linksDf = linksDf.join(linksDf.rawLink.apply(
            cleanLink).rename({0: 'cleanLink', 1: 'hashtag'}, axis=1))
        cleanLinksDf = linksDf.drop(
            labels='hashtag', axis=1).dropna().drop_duplicates()
        hashtagsDf = linksDf.drop(
            labels='cleanLink', axis=1).dropna().drop_duplicates()
        if(len(cleanLinksDf) != 0):
            resultsDfs.update(
                {'Comments Links': cleanLinksDf})
        if(len(hashtagsDf) != 0):
            resultsDfs.update(
                {'Comments Hashtags': hashtagsDf})
    return resultsDfs

def summarisedComments(resultDfs : dict):
    commentSummarisedDfDict = {'Comments Summary 🗯️' : resultDfs['Comments'][['authorDisplayName', 'authorChannelId', 'No_Unique_Videos', 'No_Comments_Made', 'Total_Likes']].sort_values(
    by=['No_Unique_Videos'], ascending = False).drop_duplicates(ignore_index = True)}
    if(resultDfs.get('Comments Links') is not None):
        commentSummarisedDfDict.update({'Links 🔗' : resultDfs['Comments Links'][['commentId','cleanLink']].groupby(by = 'cleanLink').count().sort_values(by = 'commentId', ascending = False)})
    if(resultDfs.get('Comments Hashtags') is not None):
        commentSummarisedDfDict.update({'Hashtags #️⃣': resultDfs['Comments Hashtags'][['commentId','hashtag']].groupby(by = 'hashtag').count().sort_values(by = 'commentId', ascending = False)})
    return commentSummarisedDfDict